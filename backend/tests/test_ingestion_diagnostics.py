import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chromadb
import numpy as np
from sqlmodel import Session, SQLModel, create_engine, select

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

            class EmbeddingModel:
                def encode(self, texts, normalize_embeddings=True):
                    return np.array([[1.0, 0.0] for _ in texts])

            with patch("main.engine", engine), \
                 patch("main.extract_pdf_text", return_value=[{"text": "Course notes", "page": 1}]), \
                 patch("main.extract_topics", return_value=[{
                     "name": "Foundations",
                     "summary": "Course foundations",
                     "chunk_ids": [f"{source.id}-0"],
                 }]), \
                 patch("rag.store.get_embedding_model", return_value=EmbeddingModel()), \
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
            stored = chroma_client.get_or_create_collection("studymate").get(include=["metadatas"])
            metadata = stored["metadatas"][0]
            self.assertEqual(metadata["user_id"], 23)
            self.assertIs(type(metadata["user_id"]), int)
            self.assertEqual(metadata["source_id"], source.id)
            self.assertIs(type(metadata["source_id"]), int)
            self.assertEqual(metadata["topic"], "Foundations")
            engine.dispose()

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
            collection = chroma_client.get_or_create_collection("studymate")
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


if __name__ == "__main__":
    unittest.main()
