from typing import Any, Literal

from pydantic import Field, model_validator

from tutor.groq_json import LenientGroqModel, groq_json
from rag.retriever import retrieve_chunks


Difficulty = Literal["easy", "medium", "hard"]
BloomLevel = Literal["remember", "understand", "apply"]
BLOOM_LEVELS: dict[Difficulty, BloomLevel] = {
    "easy": "remember",
    "medium": "understand",
    "hard": "apply",
}


class GeneratedQuizQuestion(LenientGroqModel):
    question: str = ""
    options: list[str] = Field(default_factory=list)
    answer_index: int = Field(default=0, ge=0, le=3)
    explanation: str = ""

    @model_validator(mode="after")
    def validate_required_fields(self) -> "GeneratedQuizQuestion":
        required = {"question", "options", "answer_index", "explanation"}
        if not required.issubset(self.model_fields_set):
            raise ValueError("Quiz question is missing required fields")
        if not self.question.strip() or not self.explanation.strip():
            raise ValueError("Quiz question and explanation cannot be empty")
        if len(self.options) != 4 or not all(option.strip() for option in self.options):
            raise ValueError("Quiz question must have four non-empty options")
        return self


class QuizQuestionsResponse(LenientGroqModel):
    questions: list[GeneratedQuizQuestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_question_count(self) -> "QuizQuestionsResponse":
        if "questions" not in self.model_fields_set or len(self.questions) != 5:
            raise ValueError("Quiz response must contain exactly five questions")
        return self


def generate_questions(
    topic: str,
    difficulty: Difficulty,
    user_id: int,
    source_ids: list[int] | None = None,
    exclude_questions: list[str] | None = None,
    subject_id: int | None = None,
) -> list[dict[str, Any]]:
    if difficulty not in ("easy", "medium", "hard"):
        raise ValueError("Difficulty must be easy, medium, or hard")
    chunks = retrieve_chunks(
        question=f"Key learning material about {topic}",
        user_id=user_id,
        limit=10,
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
        "Create exactly five accurate multiple-choice questions using only the supplied document excerpts. "
        "Return strict JSON only, with this exact shape and keys: "
        '{"questions":[{"question":"","options":["","","",""],'
        '"answer_index":0,"explanation":""}]}. '
        "Each answer_index must be an integer from 0 to 3. Do not add citations, markdown, or extra fields. "
        "Do not use outside knowledge.",
        (
            f"Selected topic: {topic}\nDifficulty: {difficulty}\n"
            f"Generate five distinct questions. Do not repeat these earlier questions: "
            f"{exclude_questions or []}\n\n"
            f"Uploaded document excerpts (use no other source):\n{context}"
        ),
        QuizQuestionsResponse,
        max_tokens=2000,
        max_attempts=2,
        log_raw_response=True,
    )
    return [
        {
            "question": item.question.strip(),
            "options": [option.strip() for option in item.options],
            "correct_index": item.answer_index,
            "explanation": item.explanation.strip(),
            "citation": chunks[index % len(chunks)]["citation"],
            "topic": topic,
            "difficulty": difficulty,
            "bloom_level": BLOOM_LEVELS[difficulty],
            "glossary": [],
        }
        for index, item in enumerate(generated_model.questions)
    ]


def generate_question(
    topic: str,
    difficulty: Difficulty,
    user_id: int,
    source_ids: list[int] | None = None,
    exclude_questions: list[str] | None = None,
    subject_id: int | None = None,
) -> dict[str, Any]:
    return generate_questions(
        topic,
        difficulty,
        user_id,
        source_ids=source_ids,
        exclude_questions=exclude_questions,
        subject_id=subject_id,
    )[0]