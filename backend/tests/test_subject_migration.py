import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
import db


class SubjectMigrationTests(unittest.TestCase):
    def test_assigns_legacy_sources_to_general_and_enforces_casefolded_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            legacy_engine = create_engine(f"sqlite:///{Path(directory) / 'legacy.db'}")
            with legacy_engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE user (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, "
                    "email VARCHAR NOT NULL, password_hash VARCHAR NOT NULL, created_at DATETIME NOT NULL)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE source (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
                    "file_name VARCHAR NOT NULL, source_type VARCHAR NOT NULL, status VARCHAR NOT NULL, "
                    "created_at DATETIME NOT NULL)"
                )
                connection.exec_driver_sql(
                    "INSERT INTO user VALUES (1, 'Learner', 'learner@example.com', 'hash', '2026-10-14')"
                )
                connection.exec_driver_sql(
                    "INSERT INTO source VALUES (10, 1, 'notes.pdf', 'pdf', 'ready', '2026-10-14')"
                )

            with patch("db.engine", legacy_engine):
                db.create_db_and_tables()

            with legacy_engine.connect() as connection:
                subject_id = connection.exec_driver_sql(
                    "SELECT subject_id FROM source WHERE id = 10"
                ).scalar_one()
                name = connection.exec_driver_sql(
                    "SELECT name FROM subject WHERE id = ?", (subject_id,)
                ).scalar_one()
            self.assertEqual(name, "General")

            with self.assertRaises(Exception):
                with legacy_engine.begin() as connection:
                    connection.exec_driver_sql(
                        "INSERT INTO subject (user_id, name, color, description, created_at) "
                        "VALUES (1, 'gENERAL', '#4f8a72', '', '2026-10-14')"
                    )
            legacy_engine.dispose()


if __name__ == "__main__":
    unittest.main()
