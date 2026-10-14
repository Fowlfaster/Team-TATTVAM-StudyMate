from typing import Literal

import chromadb
from sqlmodel import Session, select

from config import CHROMA_DIR
from db import TopicMastery


Difficulty = Literal["easy", "medium", "hard"]


def available_topics(
    user_id: int,
    source_ids: list[int] | None = None,
    topic_names: list[str] | None = None,
    subject_id: int | None = None,
) -> list[str]:
    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
        name="studymate"
    )
    filters: list[dict] = [{"user_id": user_id}]
    if subject_id is not None:
        filters.append({"subject_id": subject_id})
    if source_ids:
        filters.append({"source_id": {"$in": source_ids}})
    if topic_names:
        filters.append({"topic": {"$in": topic_names}})
    where = filters[0] if len(filters) == 1 else {"$and": filters}
    metadatas = collection.get(where=where, include=["metadatas"])["metadatas"] or []
    return sorted({
        str(metadata["topic"])
        for metadata in metadatas
        if metadata and metadata.get("topic")
    })


def ensure_mastery_topics(
    session: Session,
    user_id: int,
    source_ids: list[int] | None = None,
    topic_names: list[str] | None = None,
    subject_id: int | None = None,
) -> list[TopicMastery]:
    topics = available_topics(user_id, source_ids, topic_names, subject_id)
    existing = {
        mastery.topic: mastery
        for mastery in session.exec(
            select(TopicMastery).where(TopicMastery.user_id == user_id)
        ).all()
    }
    for topic in topics:
        if topic not in existing:
            mastery = TopicMastery(user_id=user_id, topic=topic)
            session.add(mastery)
            existing[topic] = mastery
    session.flush()
    return [existing[topic] for topic in topics]


def next_topic(
    session: Session,
    user_id: int,
    source_ids: list[int] | None = None,
    topic_names: list[str] | None = None,
    subject_id: int | None = None,
) -> TopicMastery | None:
    mastery_records = ensure_mastery_topics(session, user_id, source_ids, topic_names, subject_id)
    if not mastery_records:
        return None
    return min(mastery_records, key=lambda mastery: (mastery.score, mastery.topic))


def update_mastery(session: Session, user_id: int, topic: str, correct: bool) -> float:
    mastery = session.get(TopicMastery, (user_id, topic))
    if mastery is None:
        mastery = TopicMastery(user_id=user_id, topic=topic)
        session.add(mastery)
    if correct:
        mastery.score += 0.1 * (1 - mastery.score)
    else:
        mastery.score -= 0.15 * mastery.score
    session.add(mastery)
    session.flush()
    return mastery.score


def difficulty_for_score(score: float) -> Difficulty:
    if score < 0.4:
        return "easy"
    if score < 0.7:
        return "medium"
    return "hard"