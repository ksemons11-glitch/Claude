"""httpx wrapper with retry policy: exponential backoff + jitter, Retry-After, max 5 attempts.
401/403 raise PermanentError (credentials must be refreshed, not retried forever)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from director.jobs.worker import PermanentError, RetryableError

log = logging.getLogger("director.http")

MAX_ATTEMPTS = 5


def _retry_after(resp: httpx.Response) -> float | None:
    ra = resp.headers.get("Retry-After")
    if not ra:
        return None
    try:
        return float(ra)
    except ValueError:
        return None


class RetryingClient:
    def __init__(
        self,
        *,
        timeout: float = 60.0,
        base_backoff: float = 1.0,
        sleep=time.sleep,
        client: httpx.Client | None = None,
    ):
        self._client = client or httpx.Client(timeout=timeout)
        self._sleep = sleep
        self._base = base_backoff

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._client.request(method, url, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt >= MAX_ATTEMPTS:
                    raise RetryableError(f"transport error after {attempt} attempts: {exc}") from exc
                self._sleep(self._delay(attempt))
                continue
            if resp.status_code in (401, 403):
                raise PermanentError(
                    f"{method} {url}: HTTP {resp.status_code} - refresh credentials/permissions"
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt >= MAX_ATTEMPTS:
                    raise RetryableError(
                        f"HTTP {resp.status_code} after {attempt} attempts", retry_after=_retry_after(resp)
                    )
                self._sleep(_retry_after(resp) or self._delay(attempt))
                continue
            return resp

    def _delay(self, attempt: int) -> float:
        exp = self._base * (2 ** (attempt - 1))
        return random.uniform(exp / 2, exp)

    def close(self) -> None:
        self._client.close()
