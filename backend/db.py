from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON, inspect
from sqlmodel import Field, SQLModel, create_engine

from config import DATABASE_PATH


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subject(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    color: str = Field(default="#4f8a72")
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Source(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subject_id: int | None = Field(default=None, foreign_key="subject.id", index=True)
    file_sha256: str | None = None
    file_name: str
    source_type: str
    status: str
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Topic(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    source_id: int = Field(foreign_key="source.id", index=True)
    subject_id: int | None = Field(default=None, foreign_key="subject.id", index=True)
    name: str
    summary: str
    chunk_ids: list[str] = Field(sa_column=Column(JSON, nullable=False))


class ExplanationCache(SQLModel, table=True):
    topic_id: int = Field(primary_key=True, foreign_key="topic.id")
    level: str = Field(primary_key=True)
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class SourceAnalysisCache(SQLModel, table=True):
    source_id: int = Field(primary_key=True, foreign_key="source.id")
    level: str = Field(primary_key=True)
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class SubjectExplanationCache(SQLModel, table=True):
    cache_key: str = Field(primary_key=True)
    subject_id: int = Field(foreign_key="subject.id", index=True)
    source_id: int | None = Field(default=None, foreign_key="source.id", index=True)
    mode: str
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConceptEvaluation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    question: str
    answer: str = Field(default="")
    rubric: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    coverage: float | None = None
    accuracy: float | None = None
    clarity: float | None = None
    misconceptions: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    total_score: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuizAttempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    topic: str
    question: str
    correct: bool
    difficulty: str
    bloom_level: str = Field(default="remember")
    source_ids: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuizSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subject_id: int | None = Field(default=None, foreign_key="subject.id", index=True)
    source_id: int = Field(foreign_key="source.id", index=True)
    source_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    topic_id: int | None = Field(default=None, foreign_key="topic.id")
    topic_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    num_questions: int
    question_hashes: list[str] = Field(sa_column=Column(JSON, nullable=False))
    question_texts: list[str] = Field(sa_column=Column(JSON, nullable=False))
    answer_records: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    generated_questions: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TopicMastery(SQLModel, table=True):
    user_id: int = Field(primary_key=True, foreign_key="user.id")
    topic: str = Field(primary_key=True)
    score: float = Field(default=0.5)
    explained: bool = Field(default=False)


sqlite_url = f"sqlite:///{DATABASE_PATH.as_posix()}"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    source_columns = {column["name"] for column in inspect(engine).get_columns(Source.__tablename__)}
    if "error_message" not in source_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"ALTER TABLE {Source.__tablename__} ADD COLUMN error_message VARCHAR"
            )

    source_columns = {column["name"] for column in inspect(engine).get_columns(Source.__tablename__)}
    if "subject_id" not in source_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"ALTER TABLE {Source.__tablename__} ADD COLUMN subject_id INTEGER REFERENCES subject(id)"
            )
    source_columns = {column["name"] for column in inspect(engine).get_columns(Source.__tablename__)}
    if "file_sha256" not in source_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"ALTER TABLE {Source.__tablename__} ADD COLUMN file_sha256 VARCHAR"
            )
    topic_columns = {column["name"] for column in inspect(engine).get_columns(Topic.__tablename__)}
    if "subject_id" not in topic_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"ALTER TABLE {Topic.__tablename__} ADD COLUMN subject_id INTEGER REFERENCES subject(id)"
            )

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_subject_user_name_lower "
            "ON subject (user_id, lower(name))"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_source_subject_file_sha256 "
            "ON source (subject_id, file_sha256) WHERE file_sha256 IS NOT NULL"
        )
        users_with_unassigned_sources = connection.exec_driver_sql(
            "SELECT DISTINCT user_id FROM source WHERE subject_id IS NULL"
        ).fetchall()
        for (user_id,) in users_with_unassigned_sources:
            general = connection.exec_driver_sql(
                "SELECT id FROM subject WHERE user_id = ? AND lower(name) = lower(?)",
                (user_id, "General"),
            ).fetchone()
            if general is None:
                connection.exec_driver_sql(
                    "INSERT INTO subject (user_id, name, color, description, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, "General", "#4f8a72", "", datetime.now(timezone.utc).isoformat()),
                )
                general_id = connection.exec_driver_sql("SELECT last_insert_rowid()").scalar_one()
            else:
                general_id = general[0]
            connection.exec_driver_sql(
                "UPDATE source SET subject_id = ? WHERE user_id = ? AND subject_id IS NULL",
                (general_id, user_id),
            )
            connection.exec_driver_sql(
                "UPDATE topic SET subject_id = ? WHERE user_id = ? AND subject_id IS NULL",
                (general_id, user_id),
            )
        connection.exec_driver_sql(
            "UPDATE topic SET subject_id = (SELECT subject_id FROM source WHERE source.id = topic.source_id) "
            "WHERE subject_id IS NULL"
        )

    table_name = QuizAttempt.__tablename__
    columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
    migrations = {
        "bloom_level": "VARCHAR NOT NULL DEFAULT 'remember'",
        "source_ids": "JSON NOT NULL DEFAULT '[]'",
    }
    for column_name, definition in migrations.items():
        if column_name not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                )
            columns.add(column_name)

    quiz_session_columns = {column["name"] for column in inspect(engine).get_columns(QuizSession.__tablename__)}
    for column_name in ("source_ids", "topic_ids", "generated_questions"):
        if column_name not in quiz_session_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    f"ALTER TABLE quizsession ADD COLUMN {column_name} JSON NOT NULL DEFAULT '[]'"
                )
            quiz_session_columns.add(column_name)
    if "subject_id" not in quiz_session_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE quizsession ADD COLUMN subject_id INTEGER REFERENCES subject(id)"
            )

    mastery_columns = {column["name"] for column in inspect(engine).get_columns(TopicMastery.__tablename__)}
    if "explained" not in mastery_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE topicmastery ADD COLUMN explained BOOLEAN NOT NULL DEFAULT 0"
            )
