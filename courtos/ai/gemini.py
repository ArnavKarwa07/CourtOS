import asyncio
from collections import deque
from time import monotonic

from courtos.config import Settings

settings = Settings()

GEMINI_MODEL_NAME = settings.gemini_model
GEMINI_REQUESTS_PER_MINUTE = max(1, settings.gemini_requests_per_minute)
GEMINI_MIN_REQUEST_INTERVAL_SECONDS = 60.0 / GEMINI_REQUESTS_PER_MINUTE

_request_lock = asyncio.Lock()
_request_timestamps = deque()


async def wait_for_gemini_slot() -> None:
    """Method description.

    Args:
    *args: Arguments.
    **kwargs: Keyword arguments.

    Returns:
    Any: Return value.

    Raises:
    Exception: If an error occurs.

    """
    while True:
        async with _request_lock:
            now = monotonic()
            cutoff = now - 60.0

            while _request_timestamps and _request_timestamps[0] <= cutoff:
                _request_timestamps.popleft()

            if len(_request_timestamps) < GEMINI_REQUESTS_PER_MINUTE:
                _request_timestamps.append(now)
                return

            wait_seconds = max(0.0, 60.0 - (now - _request_timestamps[0]))

        await asyncio.sleep(wait_seconds)