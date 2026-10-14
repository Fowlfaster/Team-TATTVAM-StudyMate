from typing import Any
import json

from pydantic import BaseModel, Field

from rag.retriever import retrieve_chunks
from tutor.groq_json import LenientGroqModel, groq_json
from tutor.prompts import AnswerStyle, build_system_prompt


class AskRequest(BaseModel):
    question: str
    style: AnswerStyle = "simple"
    source_ids: list[int] = []
    topics: list[str] = []
    subject_id: int | None = None


class GeneratedAnswer(LenientGroqModel):
    answer: str = ""
    glossary: list[dict[str, str]] = Field(default_factory=list)


class Citation(BaseModel):
    n: int
    file_name: str
    source_type: str
    source_id: int | None = None
    page: int | str | None = None
    slide: int | str | None = None
    start: float | None = None
    snippet: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    glossary: list[dict[str, str]] = []


def _format_context(chunks: list[dict[str, Any]]) -> str:
    formatted_chunks = []
    for chunk in chunks:
        citation = chunk["citation"]
        location = ""
        if "page" in citation:
            location = f", page {citation['page']}"
        elif "slide" in citation:
            location = f", slide {citation['slide']}"
        elif "start" in citation:
            location = f", video at {citation['start']:.2f} seconds"
        formatted_chunks.append(
            f"[{citation['n']}] {citation['file_name']} ({citation['source_type']}{location}):\n"
            f"{chunk['text']}"
        )
    return "\n\n".join(formatted_chunks)


def answer_question(
    question: str,
    user_id: int,
    style: AnswerStyle = "simple",
    topic: str | None = None,
    source_ids: list[int] | None = None,
    topics: list[str] | None = None,
    subject_id: int | None = None,
) -> AskResponse:
    chunks = retrieve_chunks(
        question,
        user_id=user_id,
        limit=6,
        topic=topic,
        source_ids=source_ids,
        topics=topics,
        subject_id=subject_id,
    )
    if not chunks:
        return AskResponse(answer="I could not find this in your material.", citations=[])
    generated = groq_json(
        build_system_prompt(style),
        (
            f"Question: {question}\n\n"
            f"Numbered context chunks:\n{_format_context(chunks)}"
        ),
        GeneratedAnswer,
    )
    answer = str(generated.answer).strip()
    glossary = generated.glossary
    if not answer:
        raise ValueError("Groq returned an incomplete answer")
    if not isinstance(glossary, list):
        glossary = []
    citations = [Citation(**chunk["citation"]) for chunk in chunks]
    return AskResponse(answer=answer, citations=citations, glossary=glossary)