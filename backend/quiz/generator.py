from typing import Any, Literal

from pydantic import Field

from tutor.groq_json import LenientGroqModel, groq_json
from rag.retriever import retrieve_chunks


Difficulty = Literal["easy", "medium", "hard"]
BloomLevel = Literal["remember", "understand", "apply"]
BLOOM_LEVELS: dict[Difficulty, BloomLevel] = {
    "easy": "remember",
    "medium": "understand",
    "hard": "apply",
}


class QuizQuestionResponse(LenientGroqModel):
    question: str = ""
    options: list[str] = Field(default_factory=list)
    correct_index: int = 0
    explanation: str = ""
    citation: Any = 0
    bloom_level: str = ""
    glossary: list[dict[str, str]] = Field(default_factory=list)


def generate_question(
    topic: str,
    difficulty: Difficulty,
    user_id: int,
    source_ids: list[int] | None = None,
    exclude_questions: list[str] | None = None,
    subject_id: int | None = None,
) -> dict[str, Any]:
    if difficulty not in ("easy", "medium", "hard"):
        raise ValueError("Difficulty must be easy, medium, or hard")
    chunks = retrieve_chunks(
        question=f"Key learning material about {topic}",
        user_id=user_id,
        limit=6,
        topic=topic,
        source_ids=source_ids,
        subject_id=subject_id,
    )
    if not chunks:
        raise LookupError(f"No study material found for topic: {topic}")

    context = "\n\n".join(
        f"[{chunk['citation']['n']}] {chunk['citation']['file_name']} "
        f"({chunk['citation']['source_type']}):\n{chunk['text']}"
        for chunk in chunks
    )
    generated_model = groq_json(
        "Create one accurate multiple-choice question using only the supplied study material. "
        "Return JSON with question, options (four strings), correct_index (0-3), explanation, "
        "citation (supporting context number), bloom_level, and glossary [{term, definition}]. "
        "Mark terms as [[keyword]] and key sentences as {{key sentence}}. Do not use outside knowledge.",
        (
            f"Topic: {topic}\nDifficulty: {difficulty}\n"
            f"Questions already asked in this session (do not repeat): {exclude_questions or []}\n\n"
            f"Numbered study material:\n{context}"
        ),
        QuizQuestionResponse,
    )
    generated = generated_model.model_dump()
    question = str(generated["question"]).strip()
    options = generated["options"]
    correct_index = int(generated["correct_index"])
    explanation = str(generated["explanation"]).strip()
    citation_number = int(generated["citation"])

    if not question or not explanation or len(options) != 4:
        raise ValueError("Groq returned an incomplete quiz question")
    if not all(isinstance(option, str) and option.strip() for option in options):
        raise ValueError("Quiz options must be four non-empty strings")
    if correct_index not in range(4):
        raise ValueError("correct_index must be from 0 to 3")

    citation_chunk = next(
        (chunk for chunk in chunks if chunk["citation"]["n"] == citation_number),
        None,
    )
    if citation_chunk is None:
        raise ValueError("Quiz citation does not match a retrieved chunk")

    return {
        "question": question,
        "options": [option.strip() for option in options],
        "correct_index": correct_index,
        "explanation": explanation,
        "citation": citation_chunk["citation"],
        "topic": topic,
        "bloom_level": BLOOM_LEVELS[difficulty],
        "glossary": [
            {"term": str(item["term"]), "definition": str(item["definition"])}
            for item in generated.get("glossary", [])
            if isinstance(item, dict) and item.get("term") and item.get("definition")
        ],
    }