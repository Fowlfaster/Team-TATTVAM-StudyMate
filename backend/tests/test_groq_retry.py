import unittest
from unittest.mock import Mock, patch

import httpx
from groq import RateLimitError

from tutor.groq_retry import with_rate_limit_retry


def make_rate_limit_error(retry_after: str = "0") -> RateLimitError:
    response = httpx.Response(
        429,
        headers={"retry-after": retry_after},
        request=httpx.Request("POST", "https://api.groq.com"),
    )
    return RateLimitError("Rate limited", response=response, body={})


class GroqRetryTests(unittest.TestCase):
    @patch("tutor.groq_retry.time.sleep")
    def test_retries_once_and_returns_success(self, sleep: Mock) -> None:
        operation = Mock(side_effect=[make_rate_limit_error("2"), "answer"])

        result = with_rate_limit_retry(operation)

        self.assertEqual(result, "answer")
        self.assertEqual(operation.call_count, 2)
        sleep.assert_called_once_with(2.0)

    @patch("tutor.groq_retry.time.sleep")
    def test_raises_friendly_error_after_second_rate_limit(self, sleep: Mock) -> None:
        operation = Mock(side_effect=[make_rate_limit_error(), make_rate_limit_error()])

        with self.assertRaisesRegex(RuntimeError, "retried once"):
            with_rate_limit_retry(operation)

        self.assertEqual(operation.call_count, 2)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()