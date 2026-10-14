import json
from typing import Any, Literal

from pydantic import Field

from tutor.explanation import generate_topic_explanation
from tutor.groq_json import LenientGroqModel, groq_json


AnalysisLevel = Literal["beginner", "intermediate", "advanced"]


class SourceOverview(LenientGroqModel):
    title: str = ""
    overview: str = ""
    learning_objectives: list[str] = Field(default_factory=list)
    summary: str = ""
    citations: list[Any] = Field(default_factory=list)


def _unique_citations(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations = []
    seen = set()
    for section in sections:
        for citation in section["citations"]:
            key = (
                citation.get("source_id"),
                citation.get("file_name"),
                citation.get("page"),
                citation.get("slide"),
                citation.get("start"),
            )
            if key not in seen:
                seen.add(key)
                citations.append(citation)
    return citations


def analyze_source(
    source_name: str,
    level: AnalysisLevel,
    topics: list[dict[str, Any]],
    chunks_by_topic: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not topics:
        raise LookupError("This source has no extracted topics yet")

    sections = []
    for topic in topics:
        topic_id = int(topic["id"])
        chunks = chunks_by_topic.get(topic_id, [])
        if not chunks:
            raise LookupError(f"No source chunks are available for topic: {topic['name']}")
        explanation = generate_topic_explanation(topic["name"], level, chunks)
        sections.append({
            "topic_id": topic_id,
            "topic": topic["name"],
            "explanation": explanation["summary"],
            "key_points": explanation["key_points"],
            "example": explanation["example"],
            "citations": explanation["citations"],
            "glossary": explanation["glossary"],
        })

    citations = _unique_citations(sections)
    citation_numbers = {json.dumps(citation, sort_keys=True): index for index, citation in enumerate(citations, 1)}
    topic_map = [{
        "topic": section["topic"],
        "explanation": section["explanation"],
        "key_points": section["key_points"],
        "example": section["example"],
        "citations": [
            citation_numbers[json.dumps(citation, sort_keys=True)]
            for citation in section["citations"]
        ],
    } for section in sections]
    glossary_by_term = {}
    for section in sections:
        for entry in section["glossary"]:
            glossary_by_term.setdefault(entry["term"].casefold(), entry)
    glossary = list(glossary_by_term.values())

    prompt = (
        f"Create a whole-source study overview for {source_name!r} at {level} level. "
        "Use every supplied topic section; do not omit any topic. Return JSON with title, overview, "
        "learning_objectives (array), summary, and citations (array of citation numbers). The overview "
        "must be 5 to 7 complete sentences. Mark important terms as [[keyword]] and the most important "
        "sentences as {{key sentence}} (no more than 3 per section). Keep citations within the provided list.\n"
        f"Sections:\n{json.dumps(topic_map, ensure_ascii=True)}\n"
        f"Available citation numbers:\n{json.dumps(list(range(1, len(citations) + 1)))}\n"
        f"Glossary:\n{json.dumps(glossary, ensure_ascii=True)}"
    )
    system_prompt = (
        "Synthesize a course-material study overview from all mapped topic sections. "
        "Return only valid JSON matching the requested schema."
    )
    response = groq_json(system_prompt, prompt, SourceOverview)

    overview_citations = []
    for raw_citation_number in response.citations:
        try:
            citation_number = int(raw_citation_number)
        except (TypeError, ValueError):
            continue
        if 1 <= citation_number <= len(citations):
            citation = citations[citation_number - 1]
            if citation not in overview_citations:
                overview_citations.append(citation)
    if not overview_citations:
        overview_citations = citations

    return {
        **response.model_dump(exclude={"citations"}),
        "overview": response.overview or response.summary or " ".join(section["explanation"] for section in sections),
        "summary": response.summary or response.overview or " ".join(section["explanation"] for section in sections),
        "title": response.title or source_name,
        "sections": sections,
        "citations": overview_citations,
        "glossary": glossary,
    }