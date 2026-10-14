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

    @patch("tutor.groq_json.GROQ_API_KEY", "test-key")
    @patch("tutor.groq_json.Groq")
    def test_single_retry_strips_fences_and_logs_raw_response(self, groq_class: Mock) -> None:
        client = groq_class.return_value
        invalid = Mock(choices=[Mock(message=Mock(content="not json at all"), finish_reason="stop")])
        raw_json = '```json\n{"answer":"ready","items":[]}\n```'
        valid = Mock(choices=[Mock(message=Mock(content=raw_json), finish_reason="stop")])
        client.chat.completions.create.side_effect = [invalid, valid]

        with self.assertLogs("studymate.groq", level="INFO") as captured:
            result = groq_json(
                "Return a response",
                "Test",
                SampleResponse,
                max_attempts=2,
                log_raw_response=True,
            )

        self.assertEqual(result.answer, "ready")
        self.assertEqual(client.chat.completions.create.call_count, 2)
        self.assertNotIn("response_format", client.chat.completions.create.call_args_list[-1].kwargs)
        self.assertTrue(any(raw_json in entry for entry in captured.output))

    @patch("tutor.groq_json.GROQ_API_KEY", "")
    @patch("tutor.groq_json.get_groq_api_key", return_value="resolved-key")
    @patch("tutor.groq_json.Groq")
    def test_resolves_key_when_imported_value_is_empty(
        self,
        groq_class: Mock,
        _resolve_key: Mock,
    ) -> None:
        client = groq_class.return_value
        client.chat.completions.create.return_value = Mock(choices=[Mock(
            message=Mock(content=json.dumps({"answer": "ready", "items": []})),
            finish_reason="stop",
        )])

        result = groq_json("Return JSON", "Test", SampleResponse)

        self.assertEqual(result.answer, "ready")
        groq_class.assert_called_once_with(api_key="resolved-key")


if __name__ == "__main__":
    unittest.main()
