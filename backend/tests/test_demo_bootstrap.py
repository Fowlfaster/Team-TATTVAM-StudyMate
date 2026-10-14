import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlmodel import Session, select

import db
import main
from db import Source, Topic, User
from main import DEMO_EMAIL, ensure_demo_seed


class DemoBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.engine = create_engine(f"sqlite:///{root / 'demo.db'}", connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        class MemoryCollection:
            def delete(self, **kwargs):
                return None

            def add(self, **kwargs):
                return None

        class MemoryClient:
            def get_or_create_collection(self, name):
                return MemoryCollection()

        self.chroma_client = MemoryClient()
        for target, value in (
            ("db.engine", self.engine),
            ("main.engine", self.engine),
            ("main.CHROMA_DIR", root / "chroma"),
            ("main.UPLOADS_DIR", root / "uploads"),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        chroma_patcher = patch("main.chromadb.PersistentClient", return_value=self.chroma_client)
        chroma_patcher.start()
        self.addCleanup(chroma_patcher.stop)
        db.create_db_and_tables()

    def test_ensure_demo_seed_creates_demo_account_and_source(self) -> None:
        sample_dir = Path(self.temp_dir.name) / "sample_data"
        sample_dir.mkdir(parents=True, exist_ok=True)

        result = ensure_demo_seed(sample_dir)

        self.assertEqual(result["email"], DEMO_EMAIL)
        self.assertTrue(result["source_name"].endswith(".pdf"))

        with Session(self.engine) as session:
            user = session.exec(select(User).where(User.email == DEMO_EMAIL)).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.name, "Demo Learner")
            sources = session.exec(select(Source)).all()
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].user_id, user.id)
            self.assertEqual(sources[0].file_name, result["source_name"])
            self.assertEqual(sources[0].status, "ready")
            self.assertGreater(len(session.exec(select(Topic)).all()), 0)


if __name__ == "__main__":
    unittest.main()
