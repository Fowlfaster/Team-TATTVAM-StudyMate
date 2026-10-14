import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import chromadb
import numpy as np
from sqlmodel import Session, SQLModel, create_engine, select

from config import CHROMA_COLLECTION
import main
from db import Source, Topic, User


class IngestionDiagnosticsTests(unittest.TestCase):
    def make_engine(self, directory: str):
        engine = create_engine(f"sqlite:///{Path(directory) / 'diagnostics.db'}")
        SQLModel.metadata.create_all(engine)
        return engine

    def create_source(self, engine, user_id: int = 23) -> Source:
        with Session(engine) as session:
            source = Source(
                user_id=user_id,
                file_name="lecture.pdf",
                source_type="pdf",
                status="processing",
            )
            session.add(source)
            session.commit()
            session.refresh(source)
            return source

    def test_ingestion_failure_persists_stage_and_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = self.make_engine(directory)
            source = self.create_source(engine)
            with patch("main.engine", engine), \
                 patch("main.extract_pdf_text", return_value=[{"text": "Course notes", "page": 1}]), \
                 patch("main.extract_topics", side_effect=RuntimeError("GROQ_API_KEY is not configured")), \
                 self.assertLogs("main", level=logging.INFO) as captured:
                main._ingest_source(source.id, source.user_id, Path(directory) / "lecture.pdf", source.file_name, "pdf")

            with Session(engine) as session:
                saved_source = session.get(Source, source.id)
                self.assertEqual(saved_source.status, "failed")
                self.assertEqual(
                    saved_source.error_message,
                    "topic extraction: GROQ_API_KEY is not configured",
                )
            self.assertTrue(any("extracted 12 text characters" in message for message in captured.output))
            engine.dispose()

    def test_ready_ingestion_persists_topics_and_typed_chroma_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = self.make_engine(directory)
            source = self.create_source(engine)
            chroma_client = chromadb.EphemeralClient()

            with patch("main.engine", engine), \
                 patch("main.extract_pdf_text", return_value=[{"text": "Course notes", "page": 1}]), \
                 patch("main.extract_topics", return_value=[{
                     "name": "Foundations",
                     "summary": "Course foundations",
                     "chunk_ids": [f"{source.id}-0"],
                 }]), \
                 patch("rag.store.embed_texts", side_effect=lambda texts: np.array([[1.0, 0.0] for _ in texts])), \
                 patch("rag.store.chromadb.PersistentClient", return_value=chroma_client):
                main._ingest_source(
                    source.id,
                    source.user_id,
                    Path(directory) / "lecture.pdf",
                    source.file_name,
                    "pdf",
                )

            with Session(engine) as session:
                saved_source = session.get(Source, source.id)
                saved_topics = session.exec(select(Topic).where(Topic.source_id == source.id)).all()
                self.assertEqual(saved_source.status, "ready")
                self.assertIsNone(saved_source.error_message)
                self.assertEqual(len(saved_topics), 1)
            stored = chroma_client.get_or_create_collection(CHROMA_COLLECTION).get(include=["metadatas"])
            metadata = stored["metadatas"][0]
            self.assertEqual(metadata["user_id"], 23)
            self.assertIs(type(metadata["user_id"]), int)
            self.assertEqual(metadata["source_id"], source.id)
            self.assertIs(type(metadata["source_id"]), int)
            self.assertEqual(metadata["topic"], "Foundations")
            engine.dispose()

    def test_migrates_legacy_collection_with_new_embeddings(self) -> None:
        namespace = f"migration_{uuid4().hex}"
        admin_client = chromadb.EphemeralClient()
        admin_client._admin_client.create_tenant(name=namespace)
        admin_client._admin_client.create_database(name=namespace, tenant=namespace)
        chroma_client = chromadb.EphemeralClient(tenant=namespace, database=namespace)
        legacy = chroma_client.get_or_create_collection("studymate")
        legacy.add(
            ids=["2-0"],
            documents=["A thread shares its process address space."],
            metadatas=[{"user_id": 23, "source_id": 2, "topic": "Threads"}],
            embeddings=[[0.25, 0.75]],
        )
        with patch("main.CHROMA_COLLECTION", "studymate_v2"), \
             patch("main.chromadb.PersistentClient", return_value=chroma_client), \
             patch("main.embed_texts", return_value=np.array([[1.0, 0.0]])) as embed:
            main._migrate_legacy_chroma_collection()

        migrated = chroma_client.get_collection("studymate_v2").get(
            include=["documents", "metadatas", "embeddings"],
        )
        self.assertEqual(migrated["ids"], ["2-0"])
        self.assertEqual(migrated["documents"], ["A thread shares its process address space."])
        self.assertEqual(migrated["metadatas"][0]["topic"], "Threads")
        np.testing.assert_allclose(migrated["embeddings"], [[1.0, 0.0]])
        embed.assert_called_once()

    def test_debug_route_reports_owned_chroma_and_topic_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = self.make_engine(directory)
            source = self.create_source(engine, user_id=23)
            with Session(engine) as session:
                session.add(Topic(
                    user_id=23,
                    source_id=source.id,
                    name="Foundations",
                    summary="Course foundations",
                    chunk_ids=[f"{source.id}-0"],
                ))
                session.commit()

            chroma_client = chromadb.EphemeralClient()
            collection = chroma_client.get_or_create_collection(CHROMA_COLLECTION)
            collection.add(
                ids=[f"{source.id}-0"],
                embeddings=[[1.0, 0.0]],
                documents=["Course foundation text"],
                metadatas=[{
                    "user_id": 23,
                    "source_id": source.id,
                    "topic": "Foundations",
                }],
            )
            user = User(id=23, name="Learner", email="learner@example.com", password_hash="x")
            with patch("main.engine", engine), \
                 patch("main.CHROMA_DIR", root / "chroma"), \
                 patch("main.chromadb.PersistentClient", return_value=chroma_client):
                report = main.debug_source(source.id, user)
                self.assertEqual(report["status"], "processing")
                self.assertIsNone(report["error_message"])
                self.assertEqual(report["chunk_count"], 1)
                self.assertEqual(report["topic_count"], 1)
                self.assertEqual(report["sample_metadata"][0]["topic"], "Foundations")
                with self.assertRaises(Exception) as error:
                    main.debug_source(source.id, User(
                        id=99,
                        name="Other",
                        email="other@example.com",
                        password_hash="x",
                    ))
                self.assertEqual(getattr(error.exception, "status_code", None), 403)
            engine.dispose()

    def test_source_file_route_serves_uploaded_file_with_relative_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = self.make_engine(directory)
            source = self.create_source(engine, user_id=23)
            uploads_dir = root / "uploads"
            uploads_dir.mkdir()
            stored_file = uploads_dir / f"{source.id}-smoke.pdf"
            stored_file.write_bytes(b"sample pdf bytes")
            user = User(id=23, name="Learner", email="learner@example.com", password_hash="x")
            with patch("main.engine", engine), patch("main.UPLOADS_DIR", uploads_dir):
                response = main.get_source_file(source.id, user)
                source_response = main._source_response(source)

            self.assertEqual(Path(response.path), stored_file)
            self.assertEqual(source_response.file_url, f"/sources/{source.id}/file")
            self.assertNotIn("localhost", source_response.file_url)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
