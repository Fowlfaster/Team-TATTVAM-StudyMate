import json
from typing import Any, Literal

from pydantic import Field

from tutor.groq_json import LenientGroqModel, groq_json


ExplanationLevel = Literal["beginner", "intermediate", "advanced"]


class GlossaryEntry(LenientGroqModel):
    term: str = ""
    definition: str = ""


class TopicExplanationResponse(LenientGroqModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    example: str = ""
    common_mistakes: list[str] = Field(default_factory=list)
    check_question: str = ""
    citations: list[Any] = Field(default_factory=list)
    glossary: list[GlossaryEntry] = Field(default_factory=list)

LEVEL_GUIDANCE = {
    "beginner": "Use plain language, define unfamiliar terms, and build from prerequisites.",
    "intermediate": "Use standard course terminology and explain the important connections.",
    "advanced": "Include nuance, assumptions, and limitations while staying grounded in the source.",
}


def generate_topic_explanation(
    topic_name: str,
    level: ExplanationLevel,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    if not chunks:
        raise LookupError("No source chunks are available for this topic")

    numbered_chunks = [
        {"citation": chunk["citation"]["n"], "text": chunk["text"]}
        for chunk in chunks
    ]
    system_prompt = (
        "Teach the requested topic using only the supplied source chunks. "
        "Return JSON with summary (string), key_points (array of strings), "
        "example (string), common_mistakes (array of strings), "
        "check_question (string), citations (array of citation numbers), and glossary "
        "(array of {term, definition}). Mark important terms as [[keyword]] and wrap the "
        "most important sentences in {{key sentence}} (no more than 3 key sentences per section). "
        "Cite source chunk numbers that support the explanation. Do not invent facts."
    )
    user_prompt = (
        f"Topic: {topic_name}\nLevel: {level}. {LEVEL_GUIDANCE[level]}\n\n"
        f"Source chunks:\n{json.dumps(numbered_chunks, ensure_ascii=True)}"
    )
    generated = groq_json(system_prompt, user_prompt, TopicExplanationResponse).model_dump()

    citation_by_number = {
        chunk["citation"]["n"]: chunk["citation"] for chunk in chunks
    }
    citations = []
    for citation_number in generated.get("citations", []):
        try:
            citation = citation_by_number.get(int(citation_number))
        except (TypeError, ValueError):
            citation = None
        if citation is not None and citation not in citations:
            citations.append(citation)
    if not citations:
        citations = [chunks[0]["citation"]]

    summary = str(generated.get("summary", "")).strip() or f"Study the key ideas in {topic_name}."
    check_question = str(generated.get("check_question", "")).strip() or f"What is one key idea about {topic_name}?"

    return {
        "summary": summary,
        "key_points": [str(point).strip() for point in generated.get("key_points", []) if str(point).strip()],
        "example": str(generated.get("example", "")).strip(),
        "common_mistakes": [
            str(mistake).strip()
            for mistake in generated.get("common_mistakes", [])
            if str(mistake).strip()
        ],
        "check_question": check_question,
        "citations": citations,
        "glossary": generated["glossary"],
    }