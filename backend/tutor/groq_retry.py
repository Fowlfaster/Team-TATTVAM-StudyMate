import math
import time
from collections.abc import Callable
from typing import TypeVar

from groq import RateLimitError


_Result = TypeVar("_Result")
_RATE_LIMIT_MESSAGE = (
    "The AI service is temporarily rate-limited. We retried once; "
    "please wait a moment before trying again."
)


def _retry_delay_seconds(error: RateLimitError) -> float:
    retry_after = error.response.headers.get("retry-after")
    try:
        delay = float(retry_after)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(delay):
        return 1.0
    return min(max(delay, 0.0), 5.0)


def with_rate_limit_retry(operation: Callable[[], _Result]) -> _Result:
    for attempt in range(2):
        try:
            return operation()
        except RateLimitError as error:
            if attempt == 1:
                raise RuntimeError(_RATE_LIMIT_MESSAGE) from error
            delay = _retry_delay_seconds(error)
            if delay:
                time.sleep(delay)

    raise RuntimeError(_RATE_LIMIT_MESSAGE)