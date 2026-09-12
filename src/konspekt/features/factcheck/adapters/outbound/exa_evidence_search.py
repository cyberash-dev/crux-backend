import logging
import threading
import time
from collections.abc import Callable

import httpx

from konspekt.features.factcheck.domain.evidence import Evidence
from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.features.factcheck.ports.outbound.search_credits_exhausted_error import (
    SearchCreditsExhaustedError,
)

EXA_SEARCH_URL = "https://api.exa.ai/search"

_REQUEST_TIMEOUT_SECONDS = 30.0
_RESULTS_PER_QUERY = 5
_HIGHLIGHT_MAX_CHARACTERS = 2000
_MIN_REQUEST_INTERVAL_SECONDS = 1 / 8
_RETRY_BACKOFF_SECONDS = (1.0, 2.0)
_RETRYABLE_STATUS_CODES = frozenset({429, 503})
_CREDENTIAL_STATUS_CODES = frozenset({401, 403})
_CREDITS_EXHAUSTED_STATUS_CODE = 402

_logger = logging.getLogger(__name__)


class ExaEvidenceSearch:
    def __init__(
        self,
        api_key: str,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api_key = api_key
        self._http_client = http_client or httpx.Client()
        self._sleep = sleep
        self._monotonic = monotonic
        self._request_slot_lock = threading.Lock()
        self._next_request_start = float("-inf")

    def search(self, query: str) -> list[Evidence]:
        try:
            response = self._response_after_retries(query)
        except httpx.HTTPError as error:
            _logger.warning(
                "factcheck.exa_search_failed",
                extra={"query": query, "error": type(error).__name__},
            )
            return []
        _raise_for_account_status(response)
        if not response.is_success:
            _logger.warning(
                "factcheck.exa_search_failed",
                extra={"query": query, "status_code": response.status_code},
            )
            return []
        try:
            payload = response.json()
        except ValueError as error:
            _logger.warning(
                "factcheck.exa_search_malformed",
                extra={"query": query, "error": type(error).__name__},
            )
            return []
        return _evidence_list(payload)

    def _response_after_retries(self, query: str) -> httpx.Response:
        response = self._response(query)
        for backoff_seconds in _RETRY_BACKOFF_SECONDS:
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                return response
            self._sleep(_retry_delay_seconds(response, backoff_seconds))
            response = self._response(query)
        return response

    def _response(self, query: str) -> httpx.Response:
        self._wait_for_request_slot()
        return self._http_client.post(
            EXA_SEARCH_URL,
            headers={"x-api-key": self._api_key},
            json=_request_body(query),
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )

    def _wait_for_request_slot(self) -> None:
        with self._request_slot_lock:
            wait_seconds = self._next_request_start - self._monotonic()
            if wait_seconds > 0:
                self._sleep(wait_seconds)
            self._next_request_start = self._monotonic() + _MIN_REQUEST_INTERVAL_SECONDS


def _request_body(query: str) -> dict[str, object]:
    return {
        "query": query,
        "type": "auto",
        "numResults": _RESULTS_PER_QUERY,
        "contents": {
            "highlights": {"query": query, "maxCharacters": _HIGHLIGHT_MAX_CHARACTERS}
        },
    }


def _raise_for_account_status(response: httpx.Response) -> None:
    if response.status_code in _CREDENTIAL_STATUS_CODES:
        raise SearchCredentialError(f"Exa responded with HTTP {response.status_code}")
    if response.status_code == _CREDITS_EXHAUSTED_STATUS_CODE:
        raise SearchCreditsExhaustedError(
            f"Exa credits are exhausted (HTTP {_CREDITS_EXHAUSTED_STATUS_CODE})"
        )


def _retry_delay_seconds(response: httpx.Response, backoff_seconds: float) -> float:
    retry_after = response.headers.get("retry-after", "")
    return float(retry_after) if retry_after.isdecimal() else backoff_seconds


def _evidence_list(payload: object) -> list[Evidence]:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    evidence_items = (_evidence_item(result) for result in results)
    return [item for item in evidence_items if item is not None]


def _evidence_item(result: object) -> Evidence | None:
    if not isinstance(result, dict):
        return None
    url = _text(result.get("url"))
    if url is None:
        return None
    return Evidence(
        url=url,
        title=_text(result.get("title")) or "",
        published_date=_text(result.get("publishedDate")),
        excerpts=_excerpts(result.get("highlights")),
    )


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _excerpts(highlights: object) -> tuple[str, ...]:
    if not isinstance(highlights, list):
        return ()
    return tuple(highlight for highlight in highlights if isinstance(highlight, str))
