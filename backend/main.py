import logging
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Literal
from uuid import uuid4

import chromadb
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from auth import get_current_user, hash_password, router as auth_router
from config import CHROMA_COLLECTION, CHROMA_DIR, DATABASE_PATH, FRONTEND_ORIGINS, UPLOADS_DIR
from db import ConceptEvaluation, ExplanationCache, QuizAttempt, QuizSession, Source, SourceAnalysisCache, Subject, SubjectExplanationCache, Topic, TopicMastery, User, create_db_and_tables, engine
from ingest.pdf import extract_pdf_text
from ingest.slides import extract_slide_text
from ingest.video import transcribe_video
from ingest.youtube import download_youtube_audio
from rag.chunker import chunk_pieces
from rag.embeddings import embed_texts
from rag.store import store_chunks
from topic_extractor import extract_topics
from quiz.adaptive import (
    difficulty_for_score,
    ensure_mastery_topics,
    next_topic,
    update_mastery,
)
from quiz.generator import generate_questions
from ranking import rank_topics
from tutor.qa import AskRequest, AskResponse, answer_question
from tutor.explanation import generate_topic_explanation
from tutor.concept_evaluation import generate_evaluation_question, grade_evaluation_answer
from tutor.source_analysis import analyze_source
from tutor.explain_modes import elaborate_further, explain_key_topic, explain_key_topics, explain_simply


VIDEO_EXTENSIONS = {
    ".avi", ".flv", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4",
    ".mpeg", ".mpg", ".wav", ".webm", ".wmv",
}

logger = logging.getLogger(__name__)

DEMO_NAME = "Demo Learner"
DEMO_EMAIL = "demo@studymate.ai"
DEMO_PASSWORD = "studymate123"
SAMPLE_DATA_DIR = Path(__file__).resolve().parent / "sample_data"


def _build_demo_pdf(path: Path) -> None:
    objects: list[str] = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 180] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        "<< /Length 95 >>\nstream\nBT\n/F1 16 Tf\n30 90 Td\n(StudyMate demo notes: active recall, spaced repetition, and retrieval practice.) Tj\nET\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1"))
    path.write_bytes(pdf)


def _seed_demo_topics_for_source(source_id: int, user_id: int, file_name: str) -> None:
    with Session(engine) as session:
        source = session.get(Source, source_id)
        subject_id = int(source.subject_id) if source and source.subject_id is not None else None

    demo_sections = [
        {
            "name": "Active Recall",
            "summary": "Recall from memory before checking notes to strengthen retrieval and reduce forgetting.",
            "chunks": [
                "Active recall asks the learner to bring information to mind before reading the answer. This makes retrieval practice more demanding and more useful for long-term retention.",
                "When students try to explain a concept from memory, they notice gaps sooner and can target the exact area that needs review.",
            ],
        },
        {
            "name": "Spaced Repetition",
            "summary": "Reviewing information across spaced intervals reinforces memory more effectively than cramming.",
            "chunks": [
                "Spaced repetition spreads study across time so the memory is reactivated at moments when forgetting starts to occur.",
                "Short, repeated sessions are stronger than one long burst because they increase the chance of successful retrieval at the right time.",
            ],
        },
        {
            "name": "Interleaving",
            "summary": "Mixing related ideas helps learners compare patterns and choose the right strategy in different situations.",
            "chunks": [
                "Interleaving mixes problem types or concepts so the learner notices differences and similarities instead of treating each example as isolated.",
                "This can improve transfer because the student chooses an approach based on the situation instead of the order of practice.",
            ],
        },
        {
            "name": "Elaboration",
            "summary": "Explaining why an idea works deepens understanding and helps connect new information to prior knowledge.",
            "chunks": [
                "Elaboration asks the learner to explain the cause, process, or evidence behind a concept. This builds stronger mental models than memorizing definitions alone.",
                "By linking new information to familiar examples, the learner creates a richer explanation that is easier to retrieve later.",
            ],
        },
        {
            "name": "Dual Coding",
            "summary": "Combining words and visuals strengthens encoding and supports recall in different forms.",
            "chunks": [
                "Dual coding combines verbal explanations with diagrams, sketches, or concept maps so the learner stores the idea in more than one format.",
                "When students connect visual structure to verbal explanation, they can more easily recognize the concept in new contexts.",
            ],
        },
    ]

    chunks: list[dict[str, Any]] = []
    for index, section in enumerate(demo_sections):
        for chunk_index, text in enumerate(section["chunks"]):
            citation = {
                "n": len(chunks) + 1,
                "file_name": file_name,
                "source_type": "pdf",
                "source_id": source_id,
                "page": index + 1,
                "snippet": text,
            }
            chunks.append({
                "text": text,
                "topic": section["name"],
                "citation": citation,
            })

    embeddings = [[0.0 for _ in range(384)] for _ in chunks]

    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(name=CHROMA_COLLECTION)
    collection.delete(where={"$and": [{"user_id": user_id}, {"source_id": source_id}]})
    collection.add(
        ids=[f"{source_id}-{index}" for index in range(len(chunks))],
        documents=[chunk["text"] for chunk in chunks],
        embeddings=embeddings,
        metadatas=[{
            "n": chunk["citation"]["n"],
            "file_name": file_name,
            "source_type": "pdf",
            "source_id": source_id,
            "user_id": user_id,
            "subject_id": subject_id,
            "page": chunk["citation"]["page"],
            "topic": chunk["topic"],
        } for chunk in chunks],
    )

    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is not None:
            source.status = "ready"
            source.error_message = None
            session.add(source)
        for section in demo_sections:
            topics = session.exec(select(Topic).where(Topic.source_id == source_id, Topic.name == section["name"])).first()
            if topics is not None:
                continue
            session.add(Topic(
                user_id=user_id,
                source_id=source_id,
                subject_id=subject_id,
                name=section["name"],
                summary=section["summary"],
                chunk_ids=[f"{source_id}-{index}" for index, chunk in enumerate(chunks) if chunk["topic"] == section["name"]],
            ))
        session.commit()


def ensure_demo_seed(sample_dir: Path | None = None) -> dict[str, str | int]:
    target_dir = sample_dir or SAMPLE_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    demo_file = target_dir / "demo_learning_notes.pdf"
    if not demo_file.exists():
        _build_demo_pdf(demo_file)

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == DEMO_EMAIL)).first()
        if user is None:
            user = User(name=DEMO_NAME, email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
            session.add(user)
            session.commit()
            session.refresh(user)

        general = session.exec(
            select(Subject).where(Subject.user_id == user.id)
        ).all()
        general_subject = next((item for item in general if item.name.casefold() == "general"), None)
        if general_subject is None:
            general_subject = Subject(user_id=int(user.id), name="General")
            session.add(general_subject)
            session.commit()
            session.refresh(general_subject)

        existing = session.exec(select(Source).where(Source.user_id == user.id)).first()
        if existing is None:
            source = _create_source(demo_file.name, "pdf", int(user.id), int(general_subject.id))
            _seed_demo_topics_for_source(int(source.id), int(user.id), demo_file.name)
            return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "source_name": demo_file.name}

        if existing.status != "ready":
            existing.status = "ready"
            existing.error_message = None
            session.add(existing)
            session.commit()
            if session.exec(select(Topic).where(Topic.source_id == existing.id)).first() is None:
                _seed_demo_topics_for_source(int(existing.id), int(user.id), existing.file_name)
        return {"email": user.email, "password": DEMO_PASSWORD, "source_name": existing.file_name}


class YouTubeUpload(BaseModel):
    url: str
    subject_id: int


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#4f8a72", pattern=r"^#[0-9a-fA-F]{6}$")
    description: str = Field(default="", max_length=300)


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class SubjectResponse(BaseModel):
    id: int
    user_id: int
    name: str
    color: str
    description: str
    created_at: Any
    source_count: int


class SubjectDeleteResult(BaseModel):
    deleted: bool
    sources_removed: int


class SourceResponse(BaseModel):
    id: int
    user_id: int
    subject_id: int | None
    file_name: str
    source_type: str
    status: str
    error_message: str | None
    created_at: Any
    file_url: str


class QuizAnswerRequest(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=3)


class ExplainRequest(BaseModel):
    topic_id: int
    level: Literal["beginner", "intermediate", "advanced"]


class AnalyzeRequest(BaseModel):
    source_id: int
    level: Literal["beginner", "intermediate", "advanced"]


class SubjectExplainRequest(BaseModel):
    subject_id: int
    source_id: int | None = None
    topic_ids: list[int] = Field(default_factory=list)
    regenerate: bool = False


class KeyTopicsRequest(SubjectExplainRequest):
    max_topics: int = Field(default=5, ge=1, le=10)
class KeyTopicRetryRequest(SubjectExplainRequest):
    topic_id: int
    why_it_matters: str = "This topic is important for understanding the material."
    max_topics: int = Field(default=5, ge=1, le=10)


class ElaborateRequest(BaseModel):
    subject_id: int
    source_id: int | None = None
    topic_ids: list[int] = Field(default_factory=list)
    topic_id: int | None = None
    previous_explanation: str = Field(min_length=1)
    depth: int = Field(ge=1, le=3)
    focus: str | None = None


class QuizStartRequest(BaseModel):
    source_id: int | None = None
    source_ids: list[int] = Field(default_factory=list)
    subject_id: int | None = None
    topic_id: int | None = None
    topic_ids: list[int] = Field(default_factory=list)
    num_questions: Literal[5, 10, 15] = 5


class EvaluationQuestionRequest(BaseModel):
    topic_id: int


class EvaluationAnswerRequest(BaseModel):
    evaluation_id: int
    answer: str


ACTIVE_QUIZZES: dict[str, dict] = {}


def _question_hash(question: str) -> str:
    normalized = " ".join(question.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _source_response(source: Source) -> SourceResponse:
    return SourceResponse(
        id=int(source.id),
        user_id=source.user_id,
        subject_id=source.subject_id,
        file_name=source.file_name,
        source_type=source.source_type,
        status=source.status,
        error_message=source.error_message,
        created_at=source.created_at,
        file_url=f"/sources/{source.id}/file",
    )


def _record_explained_topics(user_id: int, topic_ids: list[int]) -> None:
    unique_topic_ids = list(dict.fromkeys(topic_ids))
    if not unique_topic_ids:
        return
    with Session(engine) as session:
        topics = session.exec(select(Topic).where(
            Topic.user_id == user_id,
            Topic.id.in_(unique_topic_ids),
        )).all()
        mastery_by_name = {
            record.topic: record
            for record in session.exec(
                select(TopicMastery).where(TopicMastery.user_id == user_id)
            ).all()
        }
        for topic in topics:
            mastery = mastery_by_name.get(topic.name)
            if mastery is None:
                mastery = TopicMastery(user_id=user_id, topic=topic.name, explained=True)
                mastery_by_name[topic.name] = mastery
            else:
                mastery.explained = True
            session.add(mastery)
        session.commit()


def _ingest_source(
    source_id: int,
    user_id: int,
    file_path: Path,
    file_name: str,
    source_type: str,
    subject_id: int | None = None,
) -> None:
    if subject_id is None:
        with Session(engine) as session:
            source = session.get(Source, source_id)
            subject_id = int(source.subject_id) if source and source.subject_id is not None else 0
    stage = "text extraction"
    chunks_stored = False
    try:
        logger.info("Source %s: starting %s text extraction", source_id, source_type)
        if source_type == "pdf":
            pieces = extract_pdf_text(file_path)
        elif source_type == "slides":
            pieces = extract_slide_text(file_path)
        elif source_type == "video":
            pieces = transcribe_video(file_path)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        extracted_text_length = sum(len(str(piece.get("text", ""))) for piece in pieces)
        logger.info(
            "Source %s: extracted %s text characters from %s pieces",
            source_id,
            extracted_text_length,
            len(pieces),
        )
        if extracted_text_length == 0:
            raise ValueError("No text could be extracted from this source")

        stage = "chunking"
        chunks = chunk_pieces(pieces, source_type=source_type)
        logger.info("Source %s: created %s chunks", source_id, len(chunks))

        stage = "topic extraction"
        topics = extract_topics(source_id, chunks)
        logger.info("Source %s: extracted %s topics", source_id, len(topics))
        topic_by_chunk: dict[str, str] = {}
        for topic in topics:
            for chunk_id in topic["chunk_ids"]:
                topic_by_chunk.setdefault(chunk_id, topic["name"])
        for index, chunk in enumerate(chunks):
            chunk["topic"] = topic_by_chunk.get(f"{source_id}-{index}", topics[0]["name"])
        stage = "ChromaDB storage"
        chunks_stored = True
        chunks_added = store_chunks(source_id, user_id, subject_id, file_name, source_type, chunks)
        logger.info("Source %s: added %s chunks to ChromaDB", source_id, chunks_added)

        stage = "topic persistence"
        with Session(engine) as session:
            source = session.get(Source, source_id)
            if source is None:
                raise ValueError(f"Source {source_id} no longer exists")
            for topic in topics:
                session.add(Topic(
                    user_id=user_id,
                    source_id=source_id,
                    subject_id=subject_id,
                    name=topic["name"],
                    summary=topic["summary"],
                    chunk_ids=topic["chunk_ids"],
                ))
            source.status = "ready"
            source.error_message = None
            session.add(source)
            session.commit()
        logger.info("Source %s: saved %s topics; status is ready", source_id, len(topics))
    except Exception as error:
        logger.exception("Source %s failed during %s", source_id, stage)
        if chunks_stored:
            try:
                collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
                    name=CHROMA_COLLECTION
                )
                collection.delete(
                    where={"$and": [{"user_id": user_id}, {"source_id": source_id}]}
                )
            except Exception:
                logger.exception("Source %s: failed to clean partial ChromaDB data", source_id)
        _mark_source_failed(source_id, stage, error)


def _mark_source_failed(source_id: int, stage: str, error: Exception) -> None:
    message = f"{stage}: {error}".strip()
    try:
        with Session(engine) as session:
            source = session.get(Source, source_id)
            if source is not None:
                source.status = "failed"
                source.error_message = message[:2000]
                session.add(source)
                session.commit()
    except Exception:
        logger.exception("Source %s: could not persist failure state", source_id)


def _run_ingest_source_safely(
    source_id: int,
    user_id: int,
    file_path: Path,
    file_name: str,
    source_type: str,
    subject_id: int | None = None,
) -> None:
    try:
        _ingest_source(source_id, user_id, file_path, file_name, source_type, subject_id)
    except Exception as error:
        logger.exception("Source %s: unexpected ingestion task failure", source_id)
        _mark_source_failed(source_id, "background task", error)


def _ingest_youtube(source_id: int, user_id: int, subject_id: int, url: str) -> None:
    audio_path = UPLOADS_DIR / f"{source_id}-{uuid4().hex}.mp3"
    try:
        logger.info("Source %s: downloading YouTube audio", source_id)
        downloaded_path = download_youtube_audio(url, audio_path)
        _run_ingest_source_safely(source_id, user_id, downloaded_path, url, "video", subject_id)
    except Exception as error:
        logger.exception("Source %s: YouTube background task failed", source_id)
        _mark_source_failed(source_id, "YouTube download", error)


def _run_ingest_youtube_safely(source_id: int, user_id: int, subject_id: int, url: str) -> None:
    try:
        _ingest_youtube(source_id, user_id, subject_id, url)
    except Exception as error:
        logger.exception("Source %s: unexpected YouTube task failure", source_id)
        _mark_source_failed(source_id, "background task", error)


def _create_source(
    file_name: str,
    source_type: str,
    user_id: int,
    subject_id: int,
    file_sha256: str | None = None,
) -> Source:
    with Session(engine) as session:
        source = Source(
            file_name=file_name,
            source_type=source_type,
            subject_id=subject_id,
            file_sha256=file_sha256,
            status="processing",
            error_message=None,
            user_id=user_id,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        return source


def _topic_chunk_context(
    source_id: int,
    user_id: int,
    chunk_ids: list[str],
) -> list[dict[str, Any]]:
    if not chunk_ids:
        return []
    with Session(engine) as session:
        source = session.get(Source, source_id)
        subject_id = source.subject_id if source is not None and source.user_id == user_id else None
    filters = [{"user_id": user_id}, {"source_id": source_id}]
    if subject_id is not None:
        filters.append({"subject_id": subject_id})
    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
        name=CHROMA_COLLECTION
    )
    stored_chunks = collection.get(
        ids=chunk_ids,
        where={"$and": filters},
        include=["documents", "metadatas"],
    )
    documents = stored_chunks.get("documents", []) or []
    metadatas = stored_chunks.get("metadatas", []) or []
    chunks = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] or {}
        source_type = metadata.get("source_type", "unknown")
        citation: dict[str, Any] = {
            "n": index + 1,
            "file_name": metadata.get("file_name", "Unknown source"),
            "source_type": source_type,
            "source_id": metadata.get("source_id"),
            "snippet": document.strip()[:280],
        }
        if source_type == "pdf" and "page_start" in metadata:
            start = metadata["page_start"]
            end = metadata.get("page_end", start)
            citation["page"] = start if start == end else f"{start}-{end}"
        elif source_type == "slides" and "slide_start" in metadata:
            start = metadata["slide_start"]
            end = metadata.get("slide_end", start)
            citation["slide"] = start if start == end else f"{start}-{end}"
        elif source_type == "video":
            citation["start"] = metadata.get("start", 0.0)
        chunks.append({"text": document, "citation": citation})
    return chunks


def _backfill_chroma_subject_metadata() -> None:
    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
        name=CHROMA_COLLECTION
    )
    with Session(engine) as session:
        sources = session.exec(select(Source)).all()
        for source in sources:
            if source.subject_id is None:
                continue
            stored = collection.get(
                where={"$and": [{"user_id": source.user_id}, {"source_id": source.id}]},
                include=["metadatas"],
            )
            ids = stored.get("ids", []) or []
            metadatas = stored.get("metadatas", []) or []
            if ids:
                collection.update(
                    ids=ids,
                    metadatas=[{**(metadata or {}), "subject_id": source.subject_id} for metadata in metadatas],
                )


def _migrate_legacy_chroma_collection() -> None:
    legacy_name = "studymate"
    if CHROMA_COLLECTION == legacy_name:
        return
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection_names = {collection.name for collection in client.list_collections()}
    if legacy_name not in collection_names:
        return

    legacy = client.get_collection(legacy_name)
    active = client.get_or_create_collection(name=CHROMA_COLLECTION)
    total = legacy.count()
    if total == 0:
        return

    logger.info("Migrating %s legacy Chroma chunks into %s", total, CHROMA_COLLECTION)
    try:
        for offset in range(0, total, 128):
            batch = legacy.get(
                limit=128,
                offset=offset,
                include=["documents", "metadatas"],
            )
            ids = batch.get("ids", []) or []
            documents = batch.get("documents", []) or []
            metadatas = batch.get("metadatas", []) or []
            existing = set(active.get(ids=ids, include=[]).get("ids", []) or [])
            missing = [index for index, chunk_id in enumerate(ids) if chunk_id not in existing]
            if not missing:
                continue
            missing_documents = [documents[index] for index in missing]
            active.upsert(
                ids=[ids[index] for index in missing],
                documents=missing_documents,
                embeddings=embed_texts(missing_documents).tolist(),
                metadatas=[metadatas[index] for index in missing],
            )
    except Exception:
        logger.exception("Could not migrate legacy Chroma chunks into %s", CHROMA_COLLECTION)
        return
    logger.info("Legacy Chroma migration completed for %s", CHROMA_COLLECTION)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    _migrate_legacy_chroma_collection()
    _backfill_chroma_subject_metadata()
    ensure_demo_seed()
    yield


app = FastAPI(title="StudyMate AI", lifespan=lifespan)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip().rstrip("/") for origin in FRONTEND_ORIGINS if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while content := file.read(1024 * 1024):
            digest.update(content)
    return digest.hexdigest()


@app.post("/upload", response_model=SourceResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject_id: int = Form(...),
    user: User = Depends(get_current_user),
) -> SourceResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required")

    file_name = Path(file.filename.replace("\\", "/")).name
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        source_type = "pdf"
    elif suffix == ".pptx":
        source_type = "slides"
    elif suffix in VIDEO_EXTENSIONS:
        source_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Supported files are PDF, PPTX, and video/audio")

    temporary_path = UPLOADS_DIR / f"{uuid4().hex}{suffix}"
    stored_path = temporary_path
    digest = hashlib.sha256()
    try:
        with temporary_path.open("wb") as destination:
            while content := await file.read(1024 * 1024):
                destination.write(content)
                digest.update(content)
        if temporary_path.stat().st_size == 0:
            temporary_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="The uploaded file is empty")
        with Session(engine) as session:
            subject = session.get(Subject, subject_id)
            if subject is None or subject.user_id != user.id:
                raise HTTPException(status_code=404, detail="Subject not found")
            existing_sources = session.exec(
                select(Source).where(
                    Source.user_id == user.id,
                    Source.subject_id == subject_id,
                ).order_by(Source.id)
            ).all()
            seen_hashes: set[str] = set()
            for existing in existing_sources:
                existing_hash = existing.file_sha256
                if not existing_hash:
                    stored_files = list(UPLOADS_DIR.glob(f"{existing.id}-*"))
                    if stored_files:
                        existing_hash = _sha256_file(stored_files[0])
                        if existing_hash not in seen_hashes:
                            existing.file_sha256 = existing_hash
                            session.add(existing)
                if existing_hash == digest.hexdigest():
                    temporary_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=409,
                        detail=f"{file_name} is already uploaded in this subject.",
                    )
                if existing_hash:
                    seen_hashes.add(existing_hash)
            session.commit()
        file_sha256 = digest.hexdigest()
        source = _create_source(file_name, source_type, int(user.id), subject_id, file_sha256)
        stored_path = UPLOADS_DIR / f"{source.id}-{uuid4().hex}{suffix}"
        temporary_path.replace(stored_path)
    except HTTPException:
        temporary_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save the uploaded file") from error
    finally:
        await file.close()

    background_tasks.add_task(
        _run_ingest_source_safely,
        int(source.id),
        int(user.id),
        stored_path,
        file_name,
        source_type,
        subject_id,
    )
    return _source_response(source)


@app.post("/upload/youtube", response_model=SourceResponse)
def upload_youtube(
    request: YouTubeUpload,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> SourceResponse:
    url = request.url.strip()
    if not url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="A valid HTTP or HTTPS URL is required")

    with Session(engine) as session:
        subject = session.get(Subject, request.subject_id)
        if subject is None or subject.user_id != user.id:
            raise HTTPException(status_code=404, detail="Subject not found")
    source = _create_source(url, "video", int(user.id), request.subject_id)
    background_tasks.add_task(
        _run_ingest_youtube_safely,
        int(source.id),
        int(user.id),
        request.subject_id,
        url,
    )
    return _source_response(source)


@app.get("/subjects", response_model=list[SubjectResponse])
def list_subjects(user: User = Depends(get_current_user)) -> list[SubjectResponse]:
    with Session(engine) as session:
        subjects = session.exec(
            select(Subject).where(Subject.user_id == user.id).order_by(Subject.created_at, Subject.id)
        ).all()
        return [
            SubjectResponse(
                **subject.model_dump(),
                source_count=len(session.exec(
                    select(Source.id).where(
                        Source.user_id == user.id,
                        Source.subject_id == subject.id,
                    )
                ).all()),
            )
            for subject in subjects
        ]


@app.post("/subjects", response_model=SubjectResponse, status_code=201)
def create_subject(
    request: SubjectCreate,
    user: User = Depends(get_current_user),
) -> SubjectResponse:
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Subject name cannot be empty")
    with Session(engine) as session:
        existing = session.exec(select(Subject).where(Subject.user_id == user.id)).all()
        if any(subject.name.casefold() == name.casefold() for subject in existing):
            raise HTTPException(status_code=409, detail="A subject with this name already exists")
        subject = Subject(
            user_id=int(user.id),
            name=name,
            color=request.color,
            description=request.description.strip(),
        )
        session.add(subject)
        session.commit()
        session.refresh(subject)
        return SubjectResponse(**subject.model_dump(), source_count=0)


@app.patch("/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    request: SubjectUpdate,
    user: User = Depends(get_current_user),
) -> SubjectResponse:
    with Session(engine) as session:
        subject = session.get(Subject, subject_id)
        if subject is None or subject.user_id != user.id:
            raise HTTPException(status_code=404, detail="Subject not found")
        if request.name is not None:
            name = request.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="Subject name cannot be empty")
            siblings = session.exec(select(Subject).where(Subject.user_id == user.id)).all()
            if any(item.id != subject_id and item.name.casefold() == name.casefold() for item in siblings):
                raise HTTPException(status_code=409, detail="A subject with this name already exists")
            subject.name = name
        if request.color is not None:
            subject.color = request.color
        session.add(subject)
        session.commit()
        session.refresh(subject)
        count = len(session.exec(
            select(Source.id).where(Source.user_id == user.id, Source.subject_id == subject_id)
        ).all())
        return SubjectResponse(**subject.model_dump(), source_count=count)


@app.delete("/subjects/{subject_id}", response_model=SubjectDeleteResult)
def delete_subject(
    subject_id: int,
    user: User = Depends(get_current_user),
) -> SubjectDeleteResult:
    with Session(engine) as session:
        subject = session.get(Subject, subject_id)
        if subject is None or subject.user_id != user.id:
            raise HTTPException(status_code=404, detail="Subject not found")
        source_ids = session.exec(
            select(Source.id).where(Source.user_id == user.id, Source.subject_id == subject_id)
        ).all()
        source_ids = [int(source_id) for source_id in source_ids]
    for source_id in source_ids:
        _delete_source_data(source_id, int(user.id))
    with Session(engine) as session:
        subject = session.get(Subject, subject_id)
        if subject is None or subject.user_id != user.id:
            raise HTTPException(status_code=404, detail="Subject not found")
        for cache in session.exec(
            select(SubjectExplanationCache).where(SubjectExplanationCache.subject_id == subject_id)
        ).all():
            session.delete(cache)
        session.delete(subject)
        session.commit()
    return SubjectDeleteResult(deleted=True, sources_removed=len(source_ids))


@app.get("/sources", response_model=list[SourceResponse])
def list_sources(
    subject_id: int | None = None,
    user: User = Depends(get_current_user),
) -> list[SourceResponse]:
    with Session(engine) as session:
        statement = select(Source).where(Source.user_id == user.id)
        if subject_id is not None:
            subject = session.get(Subject, subject_id)
            if subject is None or subject.user_id != user.id:
                raise HTTPException(status_code=404, detail="Subject not found")
            statement = statement.where(Source.subject_id == subject_id)
        return [
            _source_response(source)
            for source in session.exec(statement.order_by(Source.created_at.desc())).all()
        ]


def _delete_source_data(source_id: int, user_id: int) -> int:
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None or source.user_id != user_id:
            return 0
        source_topics = session.exec(select(Topic).where(Topic.source_id == source_id)).all()
        topic_ids = [int(topic.id) for topic in source_topics if topic.id is not None]
        for cache in session.exec(select(SourceAnalysisCache).where(SourceAnalysisCache.source_id == source_id)).all():
            session.delete(cache)
        for quiz_session in session.exec(select(QuizSession).where(QuizSession.source_id == source_id)).all():
            session.delete(quiz_session)
        for cache in session.exec(
            select(SubjectExplanationCache).where(SubjectExplanationCache.source_id == source_id)
        ).all():
            session.delete(cache)
        if topic_ids:
            for cache in session.exec(select(ExplanationCache).where(ExplanationCache.topic_id.in_(topic_ids))).all():
                session.delete(cache)
            for evaluation in session.exec(select(ConceptEvaluation).where(ConceptEvaluation.topic_id.in_(topic_ids))).all():
                session.delete(evaluation)
        for topic in source_topics:
            session.delete(topic)

        collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(name=CHROMA_COLLECTION)
        stored = collection.get(
            where={"$and": [{"user_id": user_id}, {"source_id": source_id}]},
            include=[],
        )
        chunk_ids = stored.get("ids", []) or []
        if chunk_ids:
            collection.delete(ids=chunk_ids)
        for file_path in UPLOADS_DIR.glob(f"{source_id}-*"):
            file_path.unlink(missing_ok=True)
        session.delete(source)
        session.commit()
        return len(chunk_ids)


@app.get("/sources/{source_id}/video")
@app.get("/sources/{source_id}/file")
def get_source_file(
    source_id: int,
    user: User = Depends(get_current_user),
) -> FileResponse:
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if source.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this source")
    matching_files = list(UPLOADS_DIR.glob(f"{source_id}-*"))
    if not matching_files:
        raise HTTPException(status_code=404, detail="Source file not found")
    return FileResponse(matching_files[0])


@app.get("/debug/source/{source_id}")
def debug_source(
    source_id: int,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if source.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this source")
        topic_count = len(session.exec(
            select(Topic.id).where(
                Topic.user_id == user.id,
                Topic.source_id == source_id,
            )
        ).all())
        status = source.status
        error_message = source.error_message

    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
        name=CHROMA_COLLECTION
    )
    stored = collection.get(
        where={"$and": [{"user_id": int(user.id)}, {"source_id": source_id}]},
        include=["metadatas"],
    )
    chunk_ids = stored.get("ids", []) or []
    metadatas = stored.get("metadatas", []) or []
    return {
        "source_id": source_id,
        "status": status,
        "error_message": error_message,
        "chunk_count": len(chunk_ids),
        "sample_metadata": metadatas[:2],
        "topic_count": topic_count,
    }


@app.delete("/sources/{source_id}")
def delete_source(
    source_id: int,
    user: User = Depends(get_current_user),
) -> dict[str, int | bool]:
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if source.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this source")
        if source.status == "processing":
            raise HTTPException(
                status_code=409,
                detail="This source is still processing and cannot be deleted yet",
            )
    chunks_removed = _delete_source_data(source_id, int(user.id))
    return {"deleted": True, "chunks_removed": chunks_removed}


@app.get("/sources/{source_id}/topics", response_model=list[Topic])
def get_source_topics(
    source_id: int,
    user: User = Depends(get_current_user),
) -> list[Topic]:
    with Session(engine) as session:
        source = session.get(Source, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if source.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this source")
        return list(session.exec(
            select(Topic)
            .where(Topic.source_id == source_id, Topic.user_id == user.id)
            .order_by(Topic.name)
        ).all())


@app.post("/explain")
def explain_topic(
    request: ExplainRequest,
    user: User = Depends(get_current_user),
) -> dict:
    cached_payload = None
    with Session(engine) as session:
        topic = session.get(Topic, request.topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
        if topic.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this topic")

        cache = session.get(ExplanationCache, (request.topic_id, request.level))
        if cache is not None:
            cached_payload = cache.payload
        topic_name = topic.name
        chunk_ids = topic.chunk_ids
        source_id = int(topic.source_id)

    if cached_payload is not None:
        _record_explained_topics(int(user.id), [request.topic_id])
        return cached_payload

    chunks = _topic_chunk_context(source_id, int(user.id), chunk_ids)

    try:
        explanation = generate_topic_explanation(
            topic_name,
            request.level,
            chunks,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logging.exception("Explanation generation failed for topic %s", request.topic_id)
        raise HTTPException(status_code=502, detail="Could not generate this explanation") from error

    payload = {
        "topic_id": request.topic_id,
        "topic_name": topic_name,
        "level": request.level,
        **explanation,
    }
    _record_explained_topics(int(user.id), [request.topic_id])
    with Session(engine) as session:
        session.add(ExplanationCache(
            topic_id=request.topic_id,
            level=request.level,
            payload=payload,
        ))
        session.commit()
    return payload


@app.post("/analyze")
def analyze_source_route(
    request: AnalyzeRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cached_payload = None
    with Session(engine) as session:
        source = session.get(Source, request.source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if source.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this source")
        if source.status != "ready":
            raise HTTPException(
                status_code=409,
                detail=source.error_message or "Wait for source processing to finish before analyzing it.",
            )
        cached = session.get(SourceAnalysisCache, (request.source_id, request.level))
        if cached is not None:
            cached_payload = cached.payload
        source_name = source.file_name
        topic_rows = session.exec(
            select(Topic)
            .where(Topic.source_id == request.source_id, Topic.user_id == user.id)
            .order_by(Topic.id)
        ).all()
        topics = [{"id": int(topic.id), "name": topic.name} for topic in topic_rows]
        topic_chunks = {int(topic.id): topic.chunk_ids for topic in topic_rows}

    topic_ids = [topic["id"] for topic in topics]
    if cached_payload is not None:
        _record_explained_topics(int(user.id), topic_ids)
        return cached_payload

    if not topics:
        raise HTTPException(status_code=404, detail="No topics are available for this source")
    chunks_by_topic = {
        topic_id: _topic_chunk_context(request.source_id, int(user.id), chunk_ids)
        for topic_id, chunk_ids in topic_chunks.items()
    }
    try:
        analysis = analyze_source(source_name, request.level, topics, chunks_by_topic)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Source analysis failed for source %s", request.source_id)
        raise HTTPException(status_code=502, detail=str(error) or "Source analysis failed") from error

    payload = {"source_id": request.source_id, "level": request.level, **analysis}
    _record_explained_topics(int(user.id), topic_ids)
    with Session(engine) as session:
        session.add(SourceAnalysisCache(
            source_id=request.source_id,
            level=request.level,
            payload=payload,
        ))
        session.commit()
    return payload


def _load_subject_topics(
    subject_id: int,
    source_id: int | None,
    user_id: int,
    topic_ids: list[int] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    with Session(engine) as session:
        subject = session.get(Subject, subject_id)
        if subject is None or subject.user_id != user_id:
            raise HTTPException(status_code=404, detail="Subject not found")
        if source_id is not None:
            source = session.get(Source, source_id)
            if source is None or source.user_id != user_id or source.subject_id != subject_id:
                raise HTTPException(status_code=404, detail="Source not found in this subject")
            if source.status != "ready":
                raise HTTPException(status_code=409, detail="This source is not ready yet")
        sources_statement = select(Source).where(
            Source.user_id == user_id,
            Source.subject_id == subject_id,
            Source.status == "ready",
        )
        if source_id is not None:
            sources_statement = sources_statement.where(Source.id == source_id)
        ready_sources = session.exec(sources_statement).all()
        allowed_source_ids = {int(source.id) for source in ready_sources if source.id is not None}
        topic_statement = select(Topic).where(
            Topic.user_id == user_id,
            Topic.subject_id == subject_id,
        )
        if source_id is not None:
            topic_statement = topic_statement.where(Topic.source_id == source_id)
        if topic_ids:
            topic_statement = topic_statement.where(Topic.id.in_(topic_ids))
        topic_rows = session.exec(topic_statement.order_by(Topic.id)).all()
        topic_data = [
            {
                "id": int(topic.id),
                "source_id": int(topic.source_id),
                "name": topic.name,
                "summary": topic.summary,
                "chunks": _topic_chunk_context(
                    int(topic.source_id), user_id, topic.chunk_ids,
                ),
            }
            for topic in topic_rows
            if topic.id is not None and int(topic.source_id) in allowed_source_ids
        ]
        return subject.name, topic_data


def _subject_explanation_cache_key(
    subject_id: int,
    source_id: int | None,
    mode: str,
    max_topics: int | None = None,
    topic_ids: list[int] | None = None,
) -> str:
    topic_scope = ",".join(str(topic_id) for topic_id in sorted(topic_ids or []))
    return f"{subject_id}:{source_id or 'all'}:{mode}:{max_topics or ''}:{topic_scope}"


def _save_subject_explanation(
    cache_key: str,
    subject_id: int,
    source_id: int | None,
    mode: str,
    payload: dict[str, Any],
) -> None:
    with Session(engine) as session:
        cache = session.get(SubjectExplanationCache, cache_key)
        if cache is None:
            cache = SubjectExplanationCache(
                cache_key=cache_key,
                subject_id=subject_id,
                source_id=source_id,
                mode=mode,
                payload=payload,
            )
        else:
            cache.payload = payload
        session.add(cache)
        session.commit()


@app.post("/explain/simple")
def explain_subject_simply(
    request: SubjectExplainRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cache_key = _subject_explanation_cache_key(request.subject_id, request.source_id, "simple-v2", topic_ids=request.topic_ids)
    subject_name, topics = _load_subject_topics(request.subject_id, request.source_id, int(user.id), request.topic_ids)
    cached_payload = None
    if not request.regenerate:
        with Session(engine) as session:
            cached = session.get(SubjectExplanationCache, cache_key)
            if cached is not None:
                cached_payload = cached.payload
        if cached_payload is not None:
            explained_topic_ids = [
                item["topic_id"]
                for item in cached_payload.get("topics", [])
                if not item.get("generation_failed")
            ]
            _record_explained_topics(int(user.id), explained_topic_ids)
            return cached_payload
    try:
        result = explain_simply(subject_name, topics)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Simple explanation failed for subject %s", request.subject_id)
        raise HTTPException(status_code=502, detail=str(error) or "Simple explanation failed") from error
    payload = {"subject_id": request.subject_id, "source_id": request.source_id, **result}
    explained_topic_ids = [
        item["topic_id"]
        for item in result.get("topics", [])
        if not item.get("generation_failed")
    ]
    _record_explained_topics(int(user.id), explained_topic_ids)
    _save_subject_explanation(cache_key, request.subject_id, request.source_id, "simple", payload)
    return payload


@app.post("/explain/key-topics")
def explain_subject_key_topics(
    request: KeyTopicsRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cache_key = _subject_explanation_cache_key(
        request.subject_id, request.source_id, "key-topics", request.max_topics, request.topic_ids,
    )
    subject_name, topics = _load_subject_topics(request.subject_id, request.source_id, int(user.id), request.topic_ids)
    cached_payload = None
    if not request.regenerate:
        with Session(engine) as session:
            cached = session.get(SubjectExplanationCache, cache_key)
            if cached is not None:
                cached_payload = cached.payload
        if cached_payload is not None:
            _record_explained_topics(int(user.id), [topic["id"] for topic in topics])
            return cached_payload
    try:
        result = explain_key_topics(subject_name, topics, request.max_topics)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Key-topic explanation failed for subject %s", request.subject_id)
        raise HTTPException(status_code=502, detail=str(error) or "Key-topic explanation failed") from error
    payload = {"subject_id": request.subject_id, "source_id": request.source_id, **result}
    _record_explained_topics(int(user.id), [topic["id"] for topic in topics])
    _save_subject_explanation(cache_key, request.subject_id, request.source_id, "key-topics", payload)
    return payload


@app.post("/explain/key-topics/{topic_id}/retry")
def retry_subject_key_topic(
    topic_id: int,
    request: KeyTopicRetryRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if topic_id != request.topic_id:
        raise HTTPException(status_code=422, detail="Topic ID does not match request body")
    subject_name, topics = _load_subject_topics(
        request.subject_id,
        request.source_id,
        int(user.id),
        [topic_id],
    )
    if not topics:
        raise HTTPException(status_code=404, detail="Topic not found in this subject")
    try:
        result = explain_key_topic(subject_name, topics[0], request.why_it_matters)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Key topic retry failed for topic %s", topic_id)
        raise HTTPException(status_code=502, detail=str(error) or "Key topic generation failed") from error

    _record_explained_topics(int(user.id), [topic_id])

    cache_key = _subject_explanation_cache_key(
        request.subject_id,
        request.source_id,
        "key-topics",
        request.max_topics,
        request.topic_ids,
    )
    with Session(engine) as session:
        cache = session.get(SubjectExplanationCache, cache_key)
        if cache is not None:
            payload = dict(cache.payload)
            payload["topics"] = [
                result if item.get("topic_id") == topic_id else item
                for item in payload.get("topics", [])
            ]
            cache.payload = payload
            session.add(cache)
            session.commit()
    return result


@app.post("/explain/elaborate")
def elaborate_explanation(
    request: ElaborateRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    topic_ids = [request.topic_id] if request.topic_id is not None else request.topic_ids
    subject_name, topics = _load_subject_topics(
        request.subject_id,
        request.source_id,
        int(user.id),
        topic_ids or None,
    )
    try:
        result = elaborate_further(
            subject_name,
            topics,
            request.previous_explanation,
            request.depth,
            request.focus,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Explanation elaboration failed for subject %s", request.subject_id)
        raise HTTPException(
            status_code=502,
            detail="Could not elaborate on this explanation. Please try again.",
        ) from error
    return {"depth": request.depth, **result}


@app.post("/evaluate/question")
def create_evaluation_question(
    request: EvaluationQuestionRequest,
    user: User = Depends(get_current_user),
) -> dict[str, int | str]:
    with Session(engine) as session:
        topic = session.get(Topic, request.topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
        if topic.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this topic")
        topic_name = topic.name
        source_id = int(topic.source_id)
        chunk_ids = topic.chunk_ids

    chunks = _topic_chunk_context(source_id, int(user.id), chunk_ids)
    try:
        generated = generate_evaluation_question(topic_name, chunks)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logging.exception("Evaluation question generation failed for topic %s", request.topic_id)
        raise HTTPException(status_code=502, detail="Could not generate an evaluation question") from error

    with Session(engine) as session:
        evaluation = ConceptEvaluation(
            user_id=int(user.id),
            topic_id=request.topic_id,
            question=generated["question"],
            rubric=generated["rubric"],
        )
        session.add(evaluation)
        session.commit()
        session.refresh(evaluation)
        return {"evaluation_id": int(evaluation.id), "question": evaluation.question}


@app.post("/evaluate/answer")
def submit_evaluation_answer(
    request: EvaluationAnswerRequest,
    user: User = Depends(get_current_user),
) -> dict:
    answer = request.answer.strip()
    word_count = len(answer.split())
    if word_count < 20:
        raise HTTPException(
            status_code=422,
            detail="Please write at least 20 words so I can evaluate your explanation.",
        )

    with Session(engine) as session:
        evaluation = session.get(ConceptEvaluation, request.evaluation_id)
        if evaluation is None:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        if evaluation.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this evaluation")
        if evaluation.answer:
            raise HTTPException(status_code=409, detail="This evaluation has already been submitted")
        question = evaluation.question
        rubric = evaluation.rubric

    try:
        grade = grade_evaluation_answer(question, answer, rubric)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logging.exception("Evaluation grading failed for evaluation %s", request.evaluation_id)
        raise HTTPException(status_code=502, detail="Could not grade this explanation") from error

    covered_by_idea = {item["idea"]: item["covered"] for item in grade["key_ideas"]}
    stored_rubric = [
        {**item, "covered": covered_by_idea.get(item["idea"], False)}
        for item in rubric
    ]
    with Session(engine) as session:
        evaluation = session.get(ConceptEvaluation, request.evaluation_id)
        if evaluation is None:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        if evaluation.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not own this evaluation")
        if evaluation.answer:
            raise HTTPException(status_code=409, detail="This evaluation has already been submitted")
        evaluation.answer = answer
        evaluation.rubric = stored_rubric
        evaluation.coverage = grade["coverage"]
        evaluation.accuracy = grade["accuracy"]
        evaluation.clarity = grade["clarity"]
        evaluation.misconceptions = grade["misconceptions"]
        evaluation.total_score = grade["total_score"]
        session.add(evaluation)
        session.commit()

    return {"evaluation_id": request.evaluation_id, **grade}


@app.post("/ask", response_model=AskResponse, response_model_exclude_none=True)
def ask_question_route(
    request: AskRequest,
    user: User = Depends(get_current_user),
) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    if request.subject_id is not None:
        with Session(engine) as session:
            subject = session.get(Subject, request.subject_id)
            if subject is None or subject.user_id != user.id:
                raise HTTPException(status_code=404, detail="Subject not found")
    try:
        return answer_question(
            question,
            int(user.id),
            request.style,
            source_ids=request.source_ids or None,
            topics=request.topics or None,
            subject_id=request.subject_id,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/quiz/start")
def start_quiz_session(
    request: QuizStartRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    with Session(engine) as session:
        if request.subject_id is not None:
            subject = session.get(Subject, request.subject_id)
            if subject is None or subject.user_id != user.id:
                raise HTTPException(status_code=404, detail="Subject not found")

        requested_source_ids = list(dict.fromkeys(
            [*request.source_ids, *([request.source_id] if request.source_id is not None else [])]
        ))
        requested_topic_ids = list(dict.fromkeys(
            [*request.topic_ids, *([request.topic_id] if request.topic_id is not None else [])]
        ))
        if not requested_topic_ids:
            raise HTTPException(status_code=422, detail="Select at least one topic before starting a quiz")
        if request.topic_id is not None:
            requested_topic = session.get(Topic, request.topic_id)
            if requested_topic is None or requested_topic.user_id != user.id:
                raise HTTPException(status_code=404, detail="Topic not found")
            if request.subject_id is not None and requested_topic.subject_id != request.subject_id:
                raise HTTPException(status_code=422, detail="Topic does not belong to the selected subject")
            if int(requested_topic.source_id) not in requested_source_ids:
                requested_source_ids.append(int(requested_topic.source_id))

        if not requested_source_ids and request.subject_id is not None:
            requested_source_ids = [int(source_id) for source_id in session.exec(
                select(Source.id).where(
                    Source.user_id == user.id,
                    Source.subject_id == request.subject_id,
                    Source.status == "ready",
                )
            ).all()]
        if not requested_source_ids:
            raise HTTPException(status_code=422, detail="Select a ready source or subject before starting a quiz")

        source_rows = session.exec(select(Source).where(
            Source.user_id == user.id,
            Source.id.in_(requested_source_ids),
            Source.status == "ready",
        )).all()
        source_by_id = {int(source.id): source for source in source_rows if source.id is not None}
        if set(source_by_id) != set(requested_source_ids):
            raise HTTPException(status_code=403, detail="One or more sources are unavailable")
        if request.subject_id is not None and any(
            source.subject_id != request.subject_id for source in source_rows
        ):
            raise HTTPException(status_code=422, detail="A selected source does not belong to this subject")

        topic_rows = []
        if requested_topic_ids:
            topic_rows = session.exec(select(Topic).where(
                Topic.user_id == user.id,
                Topic.id.in_(requested_topic_ids),
            )).all()
            if {int(topic.id) for topic in topic_rows if topic.id is not None} != set(requested_topic_ids):
                raise HTTPException(status_code=404, detail="One or more topics are unavailable")
            if any(int(topic.source_id) not in requested_source_ids for topic in topic_rows):
                raise HTTPException(status_code=422, detail="A selected topic is outside the selected sources")
            if request.subject_id is not None and any(topic.subject_id != request.subject_id for topic in topic_rows):
                raise HTTPException(status_code=422, detail="A selected topic does not belong to this subject")

        anchor_source_id = requested_source_ids[0]
        stored_topic_id = requested_topic_ids[0] if len(requested_topic_ids) == 1 else None
        quiz_session = QuizSession(
            id=uuid4().hex,
            user_id=int(user.id),
            subject_id=request.subject_id,
            source_id=anchor_source_id,
            source_ids=requested_source_ids,
            topic_id=stored_topic_id,
            topic_ids=requested_topic_ids,
            num_questions=request.num_questions,
            question_hashes=[],
            question_texts=[],
            answer_records=[],
        )
        session.add(quiz_session)
        session.commit()
        return {
            "session_id": quiz_session.id,
            "source_id": quiz_session.source_id,
            "source_ids": quiz_session.source_ids,
            "topic_id": quiz_session.topic_id,
            "topic_ids": quiz_session.topic_ids,
            "num_questions": quiz_session.num_questions,
        }


@app.get("/quiz/next")
def get_next_quiz(
    source_ids: list[int] | None = Query(default=None),
    topics: list[str] | None = Query(default=None),
    subject_id: int | None = None,
    source_id: int | None = None,
    topic_id: int | None = None,
    session_id: str | None = None,
    user: User = Depends(get_current_user),
) -> dict:
    exclude_questions: list[str] = []
    active_session_id = session_id
    scoped_source_ids = source_ids
    selected_topic_id: int | None = None

    with Session(engine) as session:
        if subject_id is not None:
            subject = session.get(Subject, subject_id)
            if subject is None or subject.user_id != user.id:
                raise HTTPException(status_code=404, detail="Subject not found")
        quiz_session = None
        if session_id is not None:
            quiz_session = session.get(QuizSession, session_id)
            if quiz_session is None:
                raise HTTPException(status_code=404, detail="Quiz session not found")
            if quiz_session.user_id != user.id:
                raise HTTPException(status_code=403, detail="You do not own this quiz session")
            if len(quiz_session.answer_records) >= quiz_session.num_questions:
                raise HTTPException(status_code=409, detail="This quiz session is complete")
            session_source_ids = quiz_session.source_ids or [quiz_session.source_id]
            if subject_id is not None and quiz_session.subject_id is not None and subject_id != quiz_session.subject_id:
                raise HTTPException(status_code=422, detail="Subject does not match this quiz session")
            if source_id is not None and source_id not in session_source_ids:
                raise HTTPException(status_code=422, detail="Source does not match this quiz session")
            session_topic_ids = quiz_session.topic_ids or ([quiz_session.topic_id] if quiz_session.topic_id is not None else [])
            if topic_id is not None and topic_id not in session_topic_ids:
                raise HTTPException(status_code=422, detail="Topic does not match this quiz session")
            subject_id = subject_id or quiz_session.subject_id
            source_id = source_id or (session_source_ids[0] if len(session_source_ids) == 1 else None)
            topic_id = topic_id or (session_topic_ids[0] if len(session_topic_ids) == 1 else None)
            scoped_source_ids = session_source_ids
            if session_topic_ids:
                session_topics = session.exec(select(Topic.name).where(
                    Topic.user_id == user.id,
                    Topic.id.in_(session_topic_ids),
                )).all()
                topics = list(dict.fromkeys(session_topics))
            exclude_questions = list(quiz_session.question_texts)

        if source_id is not None:
            source = session.get(Source, source_id)
            if source is None:
                raise HTTPException(status_code=404, detail="Source not found")
            if source.user_id != user.id:
                raise HTTPException(status_code=403, detail="You do not own this source")
            if subject_id is not None and source.subject_id != subject_id:
                raise HTTPException(status_code=422, detail="Source does not belong to the selected subject")
            if source.status != "ready":
                raise HTTPException(status_code=409, detail="This source is not ready for a quiz")
            if scoped_source_ids and source_id not in scoped_source_ids:
                raise HTTPException(status_code=422, detail="Source filters do not match")
            scoped_source_ids = [source_id]

        if scoped_source_ids:
            requested_sources = set(scoped_source_ids)
            owned_sources = set(session.exec(
                select(Source.id).where(
                    Source.user_id == user.id,
                    Source.id.in_(requested_sources),
                    Source.status == "ready",
                    *([Source.subject_id == subject_id] if subject_id is not None else []),
                )
            ).all())
            if owned_sources != requested_sources:
                raise HTTPException(status_code=403, detail="One or more sources are unavailable")

        if topic_id is not None:
            selected_topic = session.get(Topic, topic_id)
            if selected_topic is None or selected_topic.user_id != user.id:
                raise HTTPException(status_code=404, detail="Topic not found")
            if subject_id is not None and selected_topic.subject_id != subject_id:
                raise HTTPException(status_code=422, detail="Topic does not belong to the selected subject")
            if source_id is not None and selected_topic.source_id != source_id:
                raise HTTPException(status_code=422, detail="Topic does not belong to the selected source")
            source_id = int(selected_topic.source_id)
            scoped_source_ids = [source_id]
            topic_name = selected_topic.name
            selected_topic_id = int(selected_topic.id)
            mastery = session.get(TopicMastery, (int(user.id), topic_name))
            difficulty = difficulty_for_score(mastery.score if mastery is not None else 0.5)
        else:
            mastery = next_topic(session, int(user.id), scoped_source_ids, topics, subject_id)
            session.flush()
            if mastery is None:
                raise HTTPException(status_code=404, detail="No study material is available yet")
            topic_name = mastery.topic
            difficulty = difficulty_for_score(mastery.score)
            topic_statement = select(Topic).where(
                Topic.user_id == user.id,
                Topic.name == topic_name,
            )
            if subject_id is not None:
                topic_statement = topic_statement.where(Topic.subject_id == subject_id)
            if scoped_source_ids:
                topic_statement = topic_statement.where(Topic.source_id.in_(scoped_source_ids))
            matching_topic = session.exec(topic_statement.order_by(Topic.id)).first()
            selected_topic_id = int(matching_topic.id) if matching_topic is not None else None

        if scoped_source_ids is None:
            topic_statement = select(Topic.source_id).where(
                Topic.user_id == user.id,
                Topic.name == topic_name,
            )
            if subject_id is not None:
                topic_statement = topic_statement.where(Topic.subject_id == subject_id)
            topic_source_ids = session.exec(topic_statement).all()
            attempt_source_ids = sorted({int(value) for value in topic_source_ids})
        else:
            attempt_source_ids = sorted({int(value) for value in scoped_source_ids})

    generated = None
    queued_questions: list[dict[str, Any]] = []
    if active_session_id is not None:
        with Session(engine) as session:
            quiz_session = session.get(QuizSession, active_session_id)
            if quiz_session is None or quiz_session.user_id != user.id:
                raise HTTPException(status_code=404, detail="Quiz session not found")
            queued_questions = list(quiz_session.generated_questions or [])

    if queued_questions:
        generated = queued_questions.pop(0)
    else:
        try:
            batch = generate_questions(
                topic_name,
                difficulty,
                int(user.id),
                attempt_source_ids or None,
                exclude_questions=exclude_questions,
                subject_id=subject_id,
            )
            excluded_hashes = {_question_hash(question) for question in exclude_questions}
            unique_batch: list[dict[str, Any]] = []
            batch_hashes: set[str] = set()
            for question in batch:
                question_hash = _question_hash(question["question"])
                if question_hash not in excluded_hashes and question_hash not in batch_hashes:
                    unique_batch.append(question)
                    batch_hashes.add(question_hash)
            if not unique_batch:
                raise ValueError("The model repeated previously asked questions")
            generated = unique_batch[0]
            queued_questions = unique_batch[1:]
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except Exception as error:
            logger.exception("Quiz generation failed for topic %s", topic_name)
            raise HTTPException(
                status_code=502,
                detail="Quiz generation failed after one retry. Please try again or upload a clearer document.",
            ) from error

    generated_hash = _question_hash(generated["question"])

    question_number = None
    num_questions = None
    if active_session_id is not None and generated_hash is not None:
        with Session(engine) as session:
            quiz_session = session.get(QuizSession, active_session_id)
            if quiz_session is None or quiz_session.user_id != user.id:
                raise HTTPException(status_code=404, detail="Quiz session not found")
            if generated_hash in quiz_session.question_hashes:
                raise HTTPException(status_code=409, detail="Question already used in this quiz session")
            quiz_session.question_hashes = [*quiz_session.question_hashes, generated_hash]
            quiz_session.question_texts = [*quiz_session.question_texts, generated["question"]]
            quiz_session.generated_questions = queued_questions
            question_number = len(quiz_session.question_hashes)
            num_questions = quiz_session.num_questions
            session.add(quiz_session)
            session.commit()

    question_id = uuid4().hex
    ACTIVE_QUIZZES[question_id] = {
        "user_id": int(user.id),
        "subject_id": subject_id,
        "question": generated,
        "source_ids": attempt_source_ids,
        "topic_id": selected_topic_id,
        "session_id": active_session_id,
    }
    result = {
        "question_id": question_id,
        "topic_id": selected_topic_id,
        "topic": generated["topic"],
        "difficulty": generated["difficulty"],
        "bloom_level": generated["bloom_level"],
        "question": generated["question"],
        "options": generated["options"],
        "citation": generated["citation"],
        "glossary": generated.get("glossary", []),
    }
    if active_session_id is not None:
        result.update({
            "session_id": active_session_id,
            "question_number": question_number,
            "num_questions": num_questions,
        })
    return result


@app.post("/quiz/answer")
def submit_quiz_answer(
    request: QuizAnswerRequest,
    user: User = Depends(get_current_user),
) -> dict:
    active_quiz = ACTIVE_QUIZZES.get(request.question_id)
    if active_quiz is None or active_quiz["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Quiz question not found or already answered")
    quiz = active_quiz["question"]

    correct = request.selected_index == quiz["correct_index"]
    with Session(engine) as session:
        score = update_mastery(session, int(user.id), quiz["topic"], correct)
        re_explanation = None
        re_glossary: list[dict[str, str]] = []
        if score < 0.4:
            try:
                simpler_answer = answer_question(
                    f"Explain {quiz['topic']} in simpler terms for a student who is struggling. "
                    "Keep the explanation to 2-3 short sentences.",
                    style="simple",
                    topic=quiz["topic"],
                    user_id=int(user.id),
                    subject_id=active_quiz.get("subject_id"),
                )
                re_explanation = simpler_answer.answer
                re_glossary = simpler_answer.glossary
            except RuntimeError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error

        session.add(QuizAttempt(
            user_id=int(user.id),
            source_ids=active_quiz["source_ids"],
            topic=quiz["topic"],
            question=quiz["question"],
            correct=correct,
            difficulty=quiz["difficulty"],
            bloom_level=quiz["bloom_level"],
        ))

        session_progress = None
        quiz_session_id = active_quiz.get("session_id")
        if quiz_session_id is not None:
            quiz_session = session.get(QuizSession, quiz_session_id)
            if quiz_session is None or quiz_session.user_id != user.id:
                raise HTTPException(status_code=404, detail="Quiz session not found")
            answer_record = {
                "topic_id": active_quiz.get("topic_id"),
                "topic": quiz["topic"],
                "source_id": quiz_session.source_id,
                "correct": correct,
            }
            quiz_session.answer_records = [*quiz_session.answer_records, answer_record]
            session.add(quiz_session)
            records = quiz_session.answer_records
            answered = len(records)
            correct_count = sum(bool(record["correct"]) for record in records)
            weak_by_topic: dict[tuple[int | None, str, int], int] = {}
            for record in records:
                if not record["correct"]:
                    key = (record.get("topic_id"), record["topic"], record["source_id"])
                    weak_by_topic[key] = weak_by_topic.get(key, 0) + 1
            session_progress = {
                "session_id": quiz_session_id,
                "answered": answered,
                "total": quiz_session.num_questions,
                "completed": answered >= quiz_session.num_questions,
                "score": round(100 * correct_count / answered, 1) if answered else 0.0,
                "weak_points": [
                    {"topic_id": topic_id, "topic": topic_name, "source_id": source_id, "missed": missed}
                    for (topic_id, topic_name, source_id), missed in weak_by_topic.items()
                ],
            }
        session.commit()

    ACTIVE_QUIZZES.pop(request.question_id, None)
    response = {
        "correct": correct,
        "correct_index": quiz["correct_index"],
        "explanation": quiz["explanation"],
        "citation": quiz["citation"],
        "topic": quiz["topic"],
        "mastery_score": score,
        "next_difficulty": difficulty_for_score(score),
        "bloom_level": quiz["bloom_level"],
        "glossary": quiz.get("glossary", []),
    }
    if re_explanation is not None:
        response["re_explanation"] = re_explanation
        response["re_glossary"] = re_glossary
    if session_progress is not None:
        response["session_progress"] = session_progress
    return response


@app.get("/ranking")
def get_ranking(
    source_ids: list[int] | None = Query(default=None),
    topics: list[str] | None = Query(default=None),
    subject_id: int | None = None,
    user: User = Depends(get_current_user),
) -> dict:
    with Session(engine) as session:
        if subject_id is not None:
            subject = session.get(Subject, subject_id)
            if subject is None or subject.user_id != user.id:
                raise HTTPException(status_code=404, detail="Subject not found")
        return rank_topics(session, int(user.id), source_ids, topics, subject_id)


@app.get("/mastery")
def get_mastery(
    source_ids: list[int] | None = Query(default=None),
    topics: list[str] | None = Query(default=None),
    subject_id: int | None = None,
    user: User = Depends(get_current_user),
) -> list[dict[str, str | float]]:
    with Session(engine) as session:
        if subject_id is not None:
            subject = session.get(Subject, subject_id)
            if subject is None or subject.user_id != user.id:
                raise HTTPException(status_code=404, detail="Subject not found")
        attempts = session.exec(select(QuizAttempt).where(QuizAttempt.user_id == user.id)).all()
        attempted_topics = {
            attempt.topic
            for attempt in attempts
            if (not source_ids or set(source_ids).intersection(attempt.source_ids or []))
            and (not topics or attempt.topic in topics)
        }
        subject_topics = None
        if subject_id is not None:
            subject_topics = set(session.exec(select(Topic.name).where(
                Topic.user_id == user.id,
                Topic.subject_id == subject_id,
            )).all())
        mastery_records = session.exec(select(TopicMastery).where(
            TopicMastery.user_id == user.id,
            TopicMastery.explained.is_(True),
        )).all()
        return [
            {
                "topic": mastery.topic,
                "score": mastery.score,
                "difficulty": difficulty_for_score(mastery.score),
            }
            for mastery in sorted(
                (
                    record for record in mastery_records
                    if record.topic in attempted_topics
                    and (subject_topics is None or record.topic in subject_topics)
                ),
                key=lambda item: (item.score, item.topic),
            )
        ]
