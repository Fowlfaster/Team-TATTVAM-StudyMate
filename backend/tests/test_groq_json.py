import json
import unittest
from unittest.mock import Mock, patch

from pydantic import Field

from tutor.groq_json import LenientGroqModel, groq_json


class SampleResponse(LenientGroqModel):
    answer: str = ""
    items: list[str] = Field(default_factory=list)


class GroqJsonTests(unittest.TestCase):
    def test_normalizes_missing_null_and_scalar_list_fields(self) -> None:
        result = SampleResponse.model_validate({"answer": None, "items": "one item"})
        self.assertEqual(result.answer, "")
        self.assertEqual(result.items, ["one item"])
        self.assertEqual(SampleResponse.model_validate({"answer": "ok", "items": None}).items, [])

    @patch("tutor.groq_json.GROQ_API_KEY", "test-key")
    @patch("tutor.groq_json.Groq")
    def test_retries_invalid_json_and_uses_minimum_completion_budget(self, groq_class: Mock) -> None:
        client = groq_class.return_value
        invalid = Mock(choices=[Mock(message=Mock(content="not json"), finish_reason="stop")])
        valid = Mock(choices=[Mock(
            message=Mock(content=json.dumps({"answer": "ready", "items": "one"})),
            finish_reason="stop",
        )])
        client.chat.completions.create.side_effect = [invalid, valid]

        result = groq_json("Return a response", "Test", SampleResponse, max_tokens=1000)

        self.assertEqual(result.answer, "ready")
        self.assertEqual(result.items, ["one"])
        self.assertEqual(client.chat.completions.create.call_count, 2)
        self.assertEqual(client.chat.completions.create.call_args.kwargs["max_completion_tokens"], 4000)


if __name__ == "__main__":
    unittest.main()
