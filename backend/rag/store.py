from typing import Any

import chromadb

from config import CHROMA_COLLECTION, CHROMA_DIR
from rag.embeddings import embed_texts


def store_chunks(
    source_id: int,
    user_id: int,
    subject_id: int,
    file_name: str,
    source_type: str,
    chunks: list[dict[str, Any]],
) -> int:
    if not chunks:
        raise ValueError("No text could be extracted from this source")

    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
        name=CHROMA_COLLECTION
    )
    documents = [chunk["text"] for chunk in chunks]
    embeddings = embed_texts(documents).tolist()
    metadatas = []
    for chunk in chunks:
        topic = chunk.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("Every stored chunk must have a topic")
        metadata = {
            key: value
            for key, value in chunk.items()
            if key != "text" and value is not None
        }
        metadata.update({
            "source_id": source_id,
            "user_id": user_id,
            "subject_id": subject_id,
            "topic": topic,
            "file_name": file_name,
            "source_type": source_type,
        })
        metadatas.append(metadata)

    collection.delete(
        where={"$and": [{"user_id": user_id}, {"source_id": source_id}]}
    )
    collection.add(
        ids=[f"{source_id}-{index}" for index in range(len(chunks))],
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(chunks)