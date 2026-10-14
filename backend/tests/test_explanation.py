import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, inspect

import db
from quiz.generator import BLOOM_LEVELS
from tutor.explanation import TopicExplanationResponse, generate_topic_explanation


class ExplanationTests(unittest.TestCase):
    @patch("tutor.explanation.groq_json")
    def test_maps_model_citation_numbers_to_source_citations(self, groq_json_mock: Mock) -> None:
        groq_json_mock.return_value = TopicExplanationResponse.model_validate({
            "summary": "A concise summary.",
            "key_points": ["First point"],
            "example": "A useful example.",
            "common_mistakes": ["A common mistake."],
            "check_question": "What is the key idea?",
            "citations": [2],
        })
        citations = [
            {"n": 1, "file_name": "notes.pdf", "source_type": "pdf", "source_id": 5, "page": 1, "snippet": "First"},
            {"n": 2, "file_name": "notes.pdf", "source_type": "pdf", "source_id": 5, "page": 2, "snippet": "Second"},
        ]

        result = generate_topic_explanation(
            "Fractions",
            "beginner",
            [
                {"text": "First passage", "citation": citations[0]},
                {"text": "Second passage", "citation": citations[1]},
            ],
        )

        self.assertEqual(result["summary"], "A concise summary.")
        self.assertEqual(result["citations"], [citations[1]])

    def test_difficulty_maps_to_expected_bloom_levels(self) -> None:
        self.assertEqual(BLOOM_LEVELS, {
            "easy": "remember",
            "medium": "understand",
            "hard": "apply",
        })

    def test_adds_bloom_column_to_an_existing_quiz_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            legacy_engine = create_engine(f"sqlite:///{Path(directory) / 'legacy.db'}")
            with legacy_engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE quizattempt ("
                    "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, topic VARCHAR NOT NULL, "
                    "question VARCHAR NOT NULL, correct BOOLEAN NOT NULL, difficulty VARCHAR NOT NULL, "
                    "timestamp DATETIME NOT NULL)"
                )
                connection.exec_driver_sql(
                    "INSERT INTO quizattempt VALUES "
                    "(1, 1, 'Fractions', 'Question?', 1, 'easy', '2026-10-13T00:00:00')"
                )
            with patch("db.engine", legacy_engine):
                db.create_db_and_tables()
            column_names = {column["name"] for column in inspect(legacy_engine).get_columns("quizattempt")}
            self.assertIn("bloom_level", column_names)
            self.assertIn("source_ids", column_names)
            with legacy_engine.connect() as connection:
                bloom_level, source_ids = connection.exec_driver_sql(
                    "SELECT bloom_level, source_ids FROM quizattempt WHERE id = 1"
                ).one()
            self.assertEqual(bloom_level, "remember")
                        "summary": "A concise summary.",
                        "key_points": ["First point"],
                        "example": "A useful example.",
                        "common_mistakes": ["A common mistake."],
                        "check_question": "What is the key idea?",
                        "citations": [2],
            with legacy_engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE source ("
                    "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, file_name VARCHAR NOT NULL, "
                    "source_type VARCHAR NOT NULL, status VARCHAR NOT NULL, created_at DATETIME NOT NULL)"
                )
            with patch("db.engine", legacy_engine):
                db.create_db_and_tables()
            columns = {column["name"] for column in inspect(legacy_engine).get_columns("source")}
            self.assertIn("error_message", columns)
            legacy_engine.dispose()


if __name__ == "__main__":
    unittest.main()