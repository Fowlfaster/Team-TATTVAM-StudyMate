import json
import logging
import math
import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import numpy as np
from pydantic import Field

from config import EMBEDDING_MODEL
from tutor.groq_json import LenientGroqModel, groq_json


logger = logging.getLogger("studymate.topics")

CHUNK_BATCH_SIZE = 12
MAX_TOPICS = 15
MIN_SOURCE_CHARACTERS = 200        # less text than this = probably a scanned PDF
PROMPT_CHUNK_CHARACTERS = 1500     # trim each chunk in the prompt to save tokens
FALLBACK_CHUNKS_PER_TOPIC = 4
HINT_BONUS = 0.05                  # small boost when the LLM itself linked a chunk to a topic


# ---------- Response models (chunk_ids are now optional hints) ----------

class TopicProposal(LenientGroqModel):
    name: str = ""
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    chunk_ids: list[Any] = Field(default_factory=list)


class TopicExtractionResponse(LenientGroqModel):
    topics: list[TopicProposal] = Field(default_factory=list)


# ---------- Embeddings (used to assign chunks to topics) ----------

@lru_cache(maxsize=1)
def _embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL)


def _embed(texts: list[str]) -> np.ndarray:
    vectors = _embedding_model().encode(
        texts, normalize_embeddings=True, show_progress_bar=False
    )
    return np.asarray(vectors)


# ---------- Groq call ----------

def _request_topics(prompt: str) -> list[dict[str, Any]]:
    system_prompt = (
        "Organize course material into accurate, concise learning topics. "
        "Use only the supplied material. Return valid JSON shaped like "
        '{"topics": [{"name": str, "summary": str, "keywords": [str], "chunk_ids": [str]}]}. '
        "List topics in order of importance. For multi-page material, create a separate topic for "
        "each major concept or heading; do not collapse a chapter with several headings into one topic."
    )
    parsed = groq_json(system_prompt, prompt, TopicExtractionResponse)
    topics = [topic.model_dump() for topic in parsed.topics]
    logger.info("Groq returned %s topic proposals", len(topics))
    return topics


def _extract_batch(chunks: list[dict[str, str]], final_batch: bool) -> list[dict[str, Any]]:
    guidance = (
        "Return between 1 and 15 distinct, useful study topics. Short material may "
        "only need a few topics; do not invent topics to reach a number."
        if final_batch
        else "Return up to 8 provisional topics for this batch; similar themes will be merged later."
    )
    prompt_chunks = [
        {"chunk_id": chunk["chunk_id"], "text": chunk["text"][:PROMPT_CHUNK_CHARACTERS]}
        for chunk in chunks
    ]
    return _request_topics(
        f"{guidance}\nFor every topic give a short student-friendly summary, 3-6 keywords, "
        f"and (optionally) the chunk IDs that support it. Source material:\n"
        f"{json.dumps(prompt_chunks, ensure_ascii=True)}"
    )


# ---------- Cleaning and merging ----------

def _normalize_name(name: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", name.lower()))


def _merge_near_duplicates(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        name = str(topic.get("name", "")).strip()
        summary = str(topic.get("summary", "")).strip()
        keywords = [str(k).strip() for k in topic.get("keywords", []) if str(k).strip()]
        hint_ids = [str(c) for c in topic.get("chunk_ids", []) if str(c).strip()]
        normalized = _normalize_name(name)
        if not normalized or not summary:
            continue

        matching = next((
            current for current in merged
            if SequenceMatcher(None, normalized, _normalize_name(current["name"])).ratio() >= 0.88
        ), None)
        if matching is None:
            merged.append({"name": name, "summary": summary, "keywords": keywords, "hint_ids": hint_ids})
            continue

        matching["keywords"] = list(dict.fromkeys(matching["keywords"] + keywords))
        matching["hint_ids"] = list(dict.fromkeys(matching["hint_ids"] + hint_ids))
        if len(summary) > len(matching["summary"]):
            matching["summary"] = summary
    return merged


# ---------- Assign each chunk to its closest topic ----------

def _assign_chunks(topics: list[dict[str, Any]], chunks: list[dict[str, str]]) -> list[dict[str, Any]]:
    topic_texts = [
        f"{t['name']}. {t['summary']} Keywords: {', '.join(t['keywords'])}" for t in topics
    ]
    similarity = _embed([c["text"] for c in chunks]) @ _embed(topic_texts).T  # (chunks, topics)

    index_by_id = {chunk["chunk_id"]: i for i, chunk in enumerate(chunks)}
    for t_index, topic in enumerate(topics):
        for chunk_id in topic["hint_ids"]:
            if chunk_id in index_by_id:
                similarity[index_by_id[chunk_id], t_index] += HINT_BONUS

    best = similarity.argmax(axis=1)
    assignments: dict[int, list[int]] = {i: [] for i in range(len(topics))}
    for c_index, t_index in enumerate(best):
        assignments[int(t_index)].append(c_index)

    # Give empty topics their closest chunk, but only take it from a topic that has spares
    for t_index in range(len(topics)):
        if assignments[t_index]:
            continue
        for c_index in np.argsort(-similarity[:, t_index]):
            c_index = int(c_index)
            donor = int(best[c_index])
            if len(assignments[donor]) > 1:
                assignments[donor].remove(c_index)
                assignments[t_index].append(c_index)
                best[c_index] = t_index
                break

    return [
        {
            "name": topic["name"],
            "summary": topic["summary"],
            "chunk_ids": [chunks[i]["chunk_id"] for i in sorted(assignments[t_index])],
        }
        for t_index, topic in enumerate(topics)
        if assignments[t_index]
    ]


# ---------- Fallback when the LLM fails completely ----------

def _fallback_topics(chunks: list[dict[str, str]]) -> list[dict[str, Any]]:
    group_size = max(FALLBACK_CHUNKS_PER_TOPIC, math.ceil(len(chunks) / MAX_TOPICS))
    topics = []
    for start in range(0, len(chunks), group_size):
        group = chunks[start:start + group_size]
        first_line = next(
            (line.strip() for line in group[0]["text"].splitlines() if len(line.strip()) > 3), ""
        )
        name = " ".join(first_line.split()[:8]) or f"Part {len(topics) + 1}"
        summary = " ".join(group[0]["text"].split()[:40]) + "..."
        topics.append({"name": name, "summary": summary, "chunk_ids": [c["chunk_id"] for c in group]})
    return topics


# ---------- Main entry point ----------

def extract_topics(source_id: int, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    identified_chunks = [
        {"chunk_id": f"{source_id}-{index}", "text": str(chunk.get("text", ""))}
        for index, chunk in enumerate(chunks)
    ]
    identified_chunks = [c for c in identified_chunks if c["text"].strip()]
    if not identified_chunks:
        raise ValueError("Cannot extract topics from an empty source")

    total_characters = sum(len(c["text"].strip()) for c in identified_chunks)
    logger.info("Source %s: %d chunks, %d characters", source_id, len(identified_chunks), total_characters)
    if total_characters < MIN_SOURCE_CHARACTERS:
        raise ValueError("This file seems to be scanned images; its text could not be read")

    try:
        batches = [
            identified_chunks[i:i + CHUNK_BATCH_SIZE]
            for i in range(0, len(identified_chunks), CHUNK_BATCH_SIZE)
        ]
        candidates: list[dict[str, Any]] = []
        for batch in batches:
            candidates.extend(_extract_batch(batch, final_batch=len(batches) == 1))
        logger.info("Source %s: %d candidate topics from LLM", source_id, len(candidates))

        if len(batches) > 1:
            slim = [{"name": t["name"], "summary": t["summary"], "keywords": t.get("keywords", [])}
                    for t in candidates]
            candidates = _request_topics(
                "Merge these topic proposals into between 1 and 15 broad, useful study topics, "
                "most important first. Keep summaries short.\n"
                f"Topic proposals: {json.dumps(slim, ensure_ascii=True)}"
            )

        topics = _merge_near_duplicates(candidates)[:MAX_TOPICS]
        if not topics:
            raise ValueError("No usable topics after cleaning")

        result = _assign_chunks(topics, identified_chunks)
        logger.info("Source %s: %d topics after assignment", source_id, len(result))
        if not result:
            raise ValueError("No topics received any chunks")
        return result

    except Exception:
        logger.exception("Topic extraction failed for source %s; using fallback topics", source_id)
        fallback = _fallback_topics(identified_chunks)
        logger.info("Source %s: %d fallback topics", source_id, len(fallback))
        return fallback