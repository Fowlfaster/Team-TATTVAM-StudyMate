from typing import Any

import chromadb

from config import CHROMA_DIR
from rag.store import get_embedding_model


def retrieve_chunks(
    question: str,
    user_id: int,
    limit: int = 6,
    topic: str | None = None,
    source_ids: list[int] | None = None,
    topics: list[str] | None = None,
    subject_id: int | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
        name="studymate"
    )
    filters: list[dict[str, Any]] = [{"user_id": user_id}]
    if subject_id is not None:
        filters.append({"subject_id": subject_id})
    if source_ids:
        filters.append({"source_id": {"$in": source_ids}})
    topic_names = list(dict.fromkeys(([topic] if topic else []) + (topics or [])))
    if len(topic_names) == 1:
        filters.append({"topic": topic_names[0]})
    elif topic_names:
        filters.append({"topic": {"$in": topic_names}})
    where = filters[0] if len(filters) == 1 else {"$and": filters}
    result_count = len(collection.get(where=where, include=["metadatas"])["ids"])
    if result_count == 0:
        return []

    query_embedding = get_embedding_model().encode(
        [question], normalize_embeddings=True
    ).tolist()[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(limit, result_count),
        include=["documents", "metadatas", "distances"],
        where=where,
    )

    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []
    ids = results.get("ids", [[]])[0] or []

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
            page_start = metadata["page_start"]
            page_end = metadata.get("page_end", page_start)
            citation["page"] = page_start if page_start == page_end else f"{page_start}-{page_end}"
        elif source_type == "slides" and "slide_start" in metadata:
            slide_start = metadata["slide_start"]
            slide_end = metadata.get("slide_end", slide_start)
            citation["slide"] = slide_start if slide_start == slide_end else f"{slide_start}-{slide_end}"
        elif source_type == "video":
            citation["start"] = metadata.get("start", 0.0)

        chunks.append({
            "id": ids[index] if index < len(ids) else "",
            "text": document,
            "metadata": metadata,
            "distance": distances[index] if index < len(distances) else None,
            "citation": citation,
        })

    return chunks