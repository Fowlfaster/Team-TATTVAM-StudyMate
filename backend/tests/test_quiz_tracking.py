import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlmodel import Session

import db
import main
from db import QuizAttempt, Source, Subject, Topic, TopicMastery, User


class QuizTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.engine = create_engine(
            f"sqlite:///{Path(self.temp_dir.name) / 'tracking.db'}",
            connect_args={"check_same_thread": False},
        )
        self.addCleanup(self.engine.dispose)
        for target in ("db.engine", "main.engine"):
            patcher = patch(target, self.engine)
            patcher.start()
            self.addCleanup(patcher.stop)
        db.create_db_and_tables()

        with Session(self.engine) as session:
            self.user = User(name="Learner", email="learner@example.com", password_hash="hash")
            session.add(self.user)
            session.commit()
            session.refresh(self.user)
            self.user_id = int(self.user.id)
            subject = Subject(user_id=int(self.user.id), name="Operating Systems")
            session.add(subject)
            session.commit()
            session.refresh(subject)
            source = Source(
                user_id=int(self.user.id),
                subject_id=int(subject.id),
                file_name="threads.pdf",
                source_type="pdf",
                status="ready",
            )
            session.add(source)
            session.commit()
            session.refresh(source)
            self.source_id = int(source.id)
            self.subject_id = int(subject.id)
            self.topic = Topic(
                user_id=int(self.user.id),
                source_id=self.source_id,
                subject_id=self.subject_id,
                name="Multithreading Model",
                summary="Thread organization and execution.",
                chunk_ids=[],
            )
            session.add(self.topic)
            session.commit()
            session.refresh(self.topic)

    def test_dashboard_requires_both_explanation_and_quiz_attempt(self) -> None:
        user_id = self.user_id
        main._record_explained_topics(user_id, [int(self.topic.id)])
        with Session(self.engine) as session:
            session.add(QuizAttempt(
                user_id=user_id,
                topic="Multithreading Model",
                question="What is a thread?",
                correct=True,
                difficulty="easy",
                source_ids=[self.source_id],
                timestamp=datetime.now(timezone.utc),
            ))
            session.add(TopicMastery(user_id=user_id, topic="Explained only", explained=True))
            session.add(TopicMastery(user_id=user_id, topic="Quizzed only", explained=False))
            session.add(QuizAttempt(
                user_id=user_id,
                topic="Quizzed only",
                question="Question?",
                correct=False,
                difficulty="easy",
                timestamp=datetime.now(timezone.utc),
            ))
            session.commit()

        result = main.get_mastery(
            source_ids=None,
            topics=None,
            subject_id=None,
            user=SimpleNamespace(id=user_id),
        )

        self.assertEqual([item["topic"] for item in result], ["Multithreading Model"])

    def test_quiz_session_requires_and_persists_selected_topics(self) -> None:
        base = {
            "subject_id": self.subject_id,
            "source_ids": [self.source_id],
            "num_questions": 5,
        }
        with self.assertRaises(HTTPException) as error:
            main.start_quiz_session(main.QuizStartRequest(**base), user=SimpleNamespace(id=self.user_id))
        self.assertEqual(error.exception.status_code, 422)

        created = main.start_quiz_session(
            main.QuizStartRequest(**base, topic_ids=[int(self.topic.id)]),
            user=SimpleNamespace(id=self.user_id),
        )

        self.assertEqual(created["topic_ids"], [int(self.topic.id)])

    def test_next_question_uses_only_topics_stored_in_the_session(self) -> None:
        with Session(self.engine) as session:
            other_topic = Topic(
                user_id=self.user_id,
                source_id=self.source_id,
                subject_id=self.subject_id,
                name="Process Scheduling",
                summary="Scheduling processes.",
                chunk_ids=[],
            )
            session.add(other_topic)
            session.commit()
            session.refresh(other_topic)
            other_topic_id = int(other_topic.id)

        created = main.start_quiz_session(
            main.QuizStartRequest(
                subject_id=self.subject_id,
                source_ids=[self.source_id],
                topic_ids=[int(self.topic.id), other_topic_id],
                num_questions=5,
            ),
            user=SimpleNamespace(id=self.user_id),
        )
        generated = {
            "question": "Question?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "Because.",
            "citation": {"n": 1},
            "topic": "Multithreading Model",
            "difficulty": "easy",
            "bloom_level": "remember",
            "glossary": [],
        }
        with patch("main.next_topic", return_value=TopicMastery(
            user_id=self.user_id,
            topic="Multithreading Model",
            score=0.5,
        )) as next_topic:
            batch = [{**generated, "question": f"Question {index}?"} for index in range(5)]
            with patch("main.generate_questions", return_value=batch) as generate_questions:
                result = main.get_next_quiz(
                    source_ids=None,
                    topics=["Unselected topic"],
                    subject_id=self.subject_id,
                    source_id=None,
                    topic_id=None,
                    session_id=created["session_id"],
                    user=SimpleNamespace(id=self.user_id),
                )
                next_result = main.get_next_quiz(
                    source_ids=None,
                    topics=["Unselected topic"],
                    subject_id=self.subject_id,
                    source_id=None,
                    topic_id=None,
                    session_id=created["session_id"],
                    user=SimpleNamespace(id=self.user_id),
                )

        selected_names = next_topic.call_args.args[3]
        self.assertCountEqual(selected_names, ["Multithreading Model", "Process Scheduling"])
        self.assertEqual(result["difficulty"], "easy")
        self.assertEqual(next_result["question"], "Question 1?")
        self.assertEqual(generate_questions.call_count, 1)

    def test_existing_mastery_table_gets_explained_column(self) -> None:
        legacy_engine = create_engine(f"sqlite:///{Path(self.temp_dir.name) / 'legacy.db'}")
        with legacy_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE user (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, "
                "email VARCHAR NOT NULL, password_hash VARCHAR NOT NULL, created_at DATETIME NOT NULL)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE topicmastery (user_id INTEGER NOT NULL, topic VARCHAR NOT NULL, "
                "score FLOAT NOT NULL, PRIMARY KEY (user_id, topic))"
            )
        with patch("db.engine", legacy_engine):
            db.create_db_and_tables()

        columns = {column["name"] for column in inspect(legacy_engine).get_columns("topicmastery")}
        self.assertIn("explained", columns)
        legacy_engine.dispose()


if __name__ == "__main__":
    unittest.main()