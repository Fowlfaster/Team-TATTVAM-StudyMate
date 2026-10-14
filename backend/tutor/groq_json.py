import json
import logging
import re
from typing import Any, Type, TypeVar, get_origin

from groq import Groq
from pydantic import BaseModel, ValidationError, field_validator

from config import GROQ_API_KEY, GROQ_CHAT_MODEL
from tutor.groq_retry import with_rate_limit_retry

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger("studymate.groq")


class LenientGroqModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def normalize_optional_values(cls, value: Any, info: Any) -> Any:
        field = cls.model_fields.get(info.field_name)
        if field is None:
            return value
        if get_origin(field.annotation) is list:
            if value is None:
                return []
            return value if isinstance(value, list) else [value]
        if value is None:
            if field.default_factory is not None:
                return field.default_factory()
            if field.default is not None:
                return field.default
            return ""
        return value


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a reply, even if wrapped in ``` or extra words."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in Groq reply")
    return json.loads(text[start:end + 1])


def groq_json(system: str, user: str, model_cls: Type[T],
              max_tokens: int = 8000, temperature: float = 0.2) -> T:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    client = Groq(api_key=GROQ_API_KEY)
    last_error: Exception | None = None

    for attempt in range(3):
        kwargs = {
            "model": GROQ_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system + " Respond with one valid JSON object only."},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_completion_tokens": max(4000, max_tokens),
            "reasoning_effort": "low",  # less hidden thinking = more room for the answer
        }
        if attempt < 2:  # last attempt without strict JSON mode, then we parse it ourselves
            kwargs["response_format"] = {"type": "json_object"}

        try:
            completion = with_rate_limit_retry(lambda: client.chat.completions.create(**kwargs))
        except Exception as error:  # Groq returns 400 json_validate_failed for broken JSON
            logger.warning("Groq call failed (attempt %d): %s", attempt + 1, error)
            last_error = error
            continue

        choice = completion.choices[0]
        content = choice.message.content or ""
        logger.info("Groq attempt %d: finish_reason=%s, %d chars",
                    attempt + 1, choice.finish_reason, len(content))

        if choice.finish_reason == "length":  # answer was cut off
            max_tokens = min(max_tokens * 2, 16000)
            last_error = ValueError("Groq reply was cut off (token limit)")
            continue

        try:
            return model_cls.model_validate(_extract_json(content))
        except (json.JSONDecodeError, ValidationError, ValueError) as error:
            logger.warning("Invalid JSON (attempt %d): %s | raw: %s",
                           attempt + 1, error, content[:800])
            last_error = error
            user += "\n\nYour last reply was not valid JSON for the schema. Return valid JSON only."

    raise ValueError(f"Groq could not produce a valid response: {last_error}")