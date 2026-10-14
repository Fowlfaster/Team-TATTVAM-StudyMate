import json
import logging
from typing import Any

from pydantic import Field

from tutor.groq_json import LenientGroqModel, groq_json

logger = logging.getLogger(__name__)


class SimpleMap(LenientGroqModel):
    simple_explanation: str = ""
    everyday_analogy: str = ""


class SimpleSection(LenientGroqModel):
    topic: str = ""
    simple_explanation: str = ""
    everyday_analogy: str = ""


class GlossaryItem(LenientGroqModel):
    term: str = ""
    simple_definition: str = ""


class SimpleReduce(LenientGroqModel):
    title: str = ""
    big_picture: str = ""
    story_sections: list[SimpleSection] = Field(default_factory=list)
    how_topics_connect: str = ""
    five_things_to_remember: list[str] = Field(default_factory=list)
    glossary: list[GlossaryItem] = Field(default_factory=list)


class TopicRankingItem(LenientGroqModel):
    topic_id: int = 0
    why_it_matters: str = ""


class TopicRanking(LenientGroqModel):
    topics: list[TopicRankingItem] = Field(default_factory=list)


class KeyTopicDetail(LenientGroqModel):
    detailed_explanation: str = ""
    step_by_step: list[str] = Field(default_factory=list)
    example: str = Field(default="")
    diagram_description: str = ""
    common_mistakes: list[str] = Field(default_factory=list)
    exam_tips: list[str] = Field(default_factory=list)
    practice_question: str = ""
    citations: list[Any] = Field(default_factory=list)


def _request_json(system: str, prompt: str, response_model: type[LenientGroqModel]) -> dict[str, Any]:
    return groq_json(system, prompt, response_model).model_dump()


def _citation_map(topics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[tuple[Any, ...], int]]:
    citations: list[dict[str, Any]] = []
    indices: dict[tuple[Any, ...], int] = {}
    for topic in topics:
        for chunk in topic["chunks"]:
            citation = chunk["citation"]
            key = (
                citation.get("source_id"), citation.get("file_name"), citation.get("page"),
                citation.get("slide"), citation.get("start"), citation.get("snippet"),
            )
            if key not in indices:
                indices[key] = len(citations) + 1
                citations.append({**citation, "n": len(citations) + 1})
    return citations, indices


def _numbered_chunks(chunks: list[dict[str, Any]], citation_indices: dict[tuple[Any, ...], int]) -> list[dict[str, Any]]:
    numbered = []
    for chunk in chunks:
        citation = chunk["citation"]
        key = (
            citation.get("source_id"), citation.get("file_name"), citation.get("page"),
            citation.get("slide"), citation.get("start"), citation.get("snippet"),
        )
        numbered.append({"citation": citation_indices[key], "text": chunk["text"]})
    return numbered


def _selected_citations(numbers: list[Any], citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for raw_number in numbers:
        try:
            number = int(raw_number)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= len(citations) and citations[number - 1] not in selected:
            selected.append(citations[number - 1])
    return selected or citations


def explain_key_topic(
    subject_name: str,
    topic: dict[str, Any],
    why_it_matters: str,
) -> dict[str, Any]:
    citations, citation_indices = _citation_map([topic])
    chunks = _numbered_chunks(topic["chunks"], citation_indices)
    prompt = (
        f"Teach {topic['name']!r} in detail for a student studying {subject_name!r}. "
        "Use only supplied material. Explain jargon, mark important terms with [[keyword]] and key "
        "sentences with {{key sentence}}. Give ordered steps only when the topic is a process. "
        "Return JSON with detailed_explanation, step_by_step, example, diagram_description, "
        "common_mistakes, exam_tips, and practice_question. Do not return citations.\n"
        f"Why it matters: {why_it_matters}\nSummary: {topic['summary']}\n"
        f"Material: {json.dumps(chunks, ensure_ascii=True)}"
    )
    generated = _request_json(
        "Teach one key topic from the supplied material. Return one JSON object.",
        prompt,
        KeyTopicDetail,
    )
    return {
        "topic": topic["name"],
        "topic_id": topic["id"],
        "source_id": topic["source_id"],
        "why_it_matters": why_it_matters,
        **generated,
        "citations": citations,
        "generation_failed": False,
    }


def explain_simply(subject_name: str, topics: list[dict[str, Any]]) -> dict[str, Any]:
    if not topics:
        raise LookupError("No ready topics are available in this subject")
    citations, citation_indices = _citation_map(topics)
    mapped = []
    for topic in topics:
        chunks = _numbered_chunks(topic["chunks"], citation_indices)
        prompt = (
            f"Explain the topic {topic['name']!r} from this material in 3-4 short sentences for a beginner. "
            "Define jargon simply and use an everyday analogy. Return JSON with only "
            "simple_explanation and everyday_analogy.\n"
            f"Topic summary: {topic['summary']}\nMaterial: {json.dumps(chunks, ensure_ascii=True)}"
        )
        mapped.append({
            "topic": topic["name"],
            **_request_json(
                "Explain the supplied topic in plain beginner language. Return one JSON object.",
                prompt,
                SimpleMap,
            ),
        })

    prompt = (
        f"Connect these explanations into one simple story about {subject_name!r}. "
        "Write the big_picture in 5-6 short sentences. Avoid jargon unless immediately defined. "
        "Keep analogies everyday and consistent. Return exactly five remember-items and a small glossary. "
        "Include story_sections with topic, simple_explanation, everyday_analogy. Do not return citations.\n"
        f"Mapped topics: {json.dumps(mapped, ensure_ascii=True)}\n"
    )
    result = _request_json(
        "Connect these mapped explanations into a short, simple whole-material story. Return one JSON object.",
        prompt,
        SimpleReduce,
    )
    return {
        **result,
        "citations": citations,
    }


def explain_key_topics(subject_name: str, topics: list[dict[str, Any]], max_topics: int = 5) -> dict[str, Any]:
    if not topics:
        raise LookupError("No ready topics are available in this subject")
    limit = max(1, min(max_topics, 10))
    summaries = [{
        "topic_id": topic["id"],
        "topic": topic["name"],
        "summary": topic["summary"],
        "chunk_count": len(topic["chunks"]),
    } for topic in topics]
    ranking = _request_json(
        "Rank topics using only the supplied summaries and chunk coverage. Return one JSON object.",
        f"Rank the topics most important for understanding {subject_name!r}. Consider topic summaries "
        "and chunk_count as evidence of coverage. Return up to the requested number, most important first, "
        "as topics [{topic_id, why_it_matters}] with a concise one-line reason. Do not return citations.\n"
        f"Requested number: {limit}\nTopics: {json.dumps(summaries, ensure_ascii=True)}",
        TopicRanking,
    )
    topic_by_id = {topic["id"]: topic for topic in topics}
    ranked = [
        (topic_by_id[item["topic_id"]], item["why_it_matters"])
        for item in ranking["topics"]
        if item["topic_id"] in topic_by_id
    ][:limit]
    if not ranked:
        ranked = [(topic, "This topic is covered in the source material.") for topic in sorted(topics, key=lambda item: len(item["chunks"]), reverse=True)[:limit]]

    details = []
    for topic, why_it_matters in ranked:
        try:
            details.append(explain_key_topic(subject_name, topic, why_it_matters))
        except Exception as error:
            logger.exception("Key topic generation failed for topic %s", topic["id"])
            citations, _ = _citation_map([topic])
            details.append({
                "topic": topic["name"],
                "topic_id": topic["id"],
                "source_id": topic["source_id"],
                "why_it_matters": why_it_matters,
                "detailed_explanation": "",
                "step_by_step": [],
                "example": "",
                "diagram_description": "",
                "common_mistakes": [],
                "exam_tips": [],
                "practice_question": "",
                "citations": citations,
                "generation_failed": True,
                "generation_error": str(error),
            })
    return {"title": subject_name, "topics": details}
