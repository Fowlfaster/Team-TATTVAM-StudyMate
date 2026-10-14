import logging
import shutil
import sys
from pathlib import Path

from sqlmodel import Session, select

from config import CHROMA_DIR, DATABASE_PATH, UPLOADS_DIR
from db import Source, Subject, User, create_db_and_tables, engine
from main import VIDEO_EXTENSIONS, _create_source, _ingest_source


SAMPLE_DATA_DIR = Path(__file__).resolve().parent / "sample_data"
SUPPORTED_TYPES = {
    ".pdf": "pdf",
    ".pptx": "slides",
    **{extension: "video" for extension in VIDEO_EXTENSIONS},
}


def _source_id_for(file_path: Path, source_type: str, user_id: int) -> int | None:
    with Session(engine) as session:
        source = session.exec(
            select(Source).where(
                Source.file_name == file_path.name,
                Source.source_type == source_type,
                Source.user_id == user_id,
            )
        ).first()
        if source is not None:
            if source.status == "ready":
                return None
            source.status = "processing"
            session.add(source)
            session.commit()
            session.refresh(source)
            return int(source.id)

    with Session(engine) as session:
        subjects = session.exec(select(Subject).where(Subject.user_id == user_id)).all()
        general = next((subject for subject in subjects if subject.name.casefold() == "general"), None)
        if general is None:
            general = Subject(user_id=user_id, name="General")
            session.add(general)
            session.commit()
            session.refresh(general)
        subject_id = int(general.id)
    source = _create_source(file_path.name, source_type, user_id, subject_id)
    return int(source.id)


def main() -> int:
    SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    with Session(engine) as session:
        user = session.exec(select(User).order_by(User.id)).first()
    if user is None:
        print("Create an account in StudyMate before seeding sample data.")
        return 1

    files = sorted(
        path for path in SAMPLE_DATA_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_TYPES
    )
    if not files:
        print(
            "No supported files found in backend/sample_data/. "
            "Add PDF, PPTX, audio, or video files and run this script again."
        )
        return 0

    ready_count = 0
    failed_count = 0
    skipped_count = 0
    for file_path in files:
        source_type = SUPPORTED_TYPES[file_path.suffix.lower()]
        source_id = _source_id_for(file_path, source_type, int(user.id))
        if source_id is None:
            print(f"Skipped (already ready): {file_path.name}")
            skipped_count += 1
            continue

        ingest_path = file_path
        if source_type == "video":
            ingest_path = UPLOADS_DIR / f"{source_id}-{file_path.name}"
            try:
                shutil.copy2(file_path, ingest_path)
            except OSError:
                logging.exception("Could not copy sample video %s", file_path)

        with Session(engine) as session:
            source = session.get(Source, source_id)
            subject_id = int(source.subject_id) if source and source.subject_id is not None else 0
        _ingest_source(source_id, int(user.id), ingest_path, file_path.name, source_type, subject_id)
        with Session(engine) as session:
            source = session.get(Source, source_id)
            status = source.status if source is not None else "failed"

        print(f"{status.title()}: {file_path.name}")
        if status == "ready":
            ready_count += 1
        else:
            failed_count += 1

    print(
        f"Seed complete: {ready_count} ready, {failed_count} failed, "
        f"{skipped_count} already ready."
    )
    return 1 if failed_count else 0


if __name__ == "__main__":
    sys.exit(main())