import json
from collections.abc import Callable

import httpx
import pytest

from konspekt.features.factcheck.adapters.outbound.exa_evidence_search import ExaEvidenceSearch
from konspekt.features.factcheck.domain.evidence import Evidence
from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.features.factcheck.ports.outbound.search_credits_exhausted_error import (
    SearchCreditsExhaustedError,
)

SENTINEL_API_KEY = "exa-sentinel-key-7f3a9c"
QUERY = "merge sort worst case is n log n"


def a_recorded_response() -> dict[str, object]:
    return {
        "requestId": "b59",
        "resolvedSearchType": "neural",
        "searchTime": 812,
        "costDollars": {"total": 0.007, "search": {"neural": 0.007}},
        "results": [
            {
                "id": "https://algs4.cs.princeton.edu/22mergesort/",
                "url": "https://algs4.cs.princeton.edu/22mergesort/",
                "title": "Mergesort",
                "author": "Robert Sedgewick",
                "highlights": [
                    "Mergesort guarantees to sort an array of N items in time proportional"
                    " to N log N, no matter what the input."
                ],
            },
            {
                "id": "https://stackoverflow.com/questions/7801861",
                "url": "https://stackoverflow.com/questions/7801861/"
                "why-is-merge-sort-worst-case-run-time-o-n-log-n",
                "title": "Why is merge sort worst case run time O (n log n)?",
                "publishedDate": "2011-10-18T00:00:00.000Z",
                "highlights": [
                    "At Stage-2, each element of sublist is compared with its adjacent"
                    " sublist\n...\nso the total is n log n."
                ],
            },
        ],
    }


def a_success() -> httpx.Response:
    return httpx.Response(200, json=a_recorded_response())


NON_RETRYABLE_FAILURES = [
    pytest.param(lambda: httpx.Response(500, json=a_recorded_response()), id="500"),
    pytest.param(lambda: httpx.Response(404, json=a_recorded_response()), id="404"),
    pytest.param(lambda: httpx.ReadTimeout("timed out"), id="timeout"),
    pytest.param(lambda: httpx.ConnectError("connection refused"), id="transport-error"),
]

ACCOUNT_ERRORS = [
    (401, SearchCredentialError),
    (403, SearchCredentialError),
    (402, SearchCreditsExhaustedError),
]


class ScriptedTransport:
    def __init__(self, *outcomes: httpx.Response | httpx.HTTPError) -> None:
        self.requests: list[httpx.Request] = []
        self._outcomes = list(outcomes)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        outcome = self._outcomes[0] if len(self._outcomes) == 1 else self._outcomes.pop(0)
        if isinstance(outcome, httpx.HTTPError):
            raise outcome
        return outcome


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def a_search(transport: ScriptedTransport, clock: FakeClock) -> ExaEvidenceSearch:
    return ExaEvidenceSearch(
        api_key=SENTINEL_API_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(transport.handler)),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )


def test_recorded_response_is_mapped_to_evidence() -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(a_success())

    evidence = a_search(transport, FakeClock()).search(QUERY)

    assert evidence == [
        Evidence(
            url="https://algs4.cs.princeton.edu/22mergesort/",
            title="Mergesort",
            published_date=None,
            excerpts=(
                "Mergesort guarantees to sort an array of N items in time proportional"
                " to N log N, no matter what the input.",
            ),
        ),
        Evidence(
            url="https://stackoverflow.com/questions/7801861/"
            "why-is-merge-sort-worst-case-run-time-o-n-log-n",
            title="Why is merge sort worst case run time O (n log n)?",
            published_date="2011-10-18T00:00:00.000Z",
            excerpts=(
                "At Stage-2, each element of sublist is compared with its adjacent"
                " sublist\n...\nso the total is n log n.",
            ),
        ),
    ]


def test_request_follows_the_consumer_contract() -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(a_success())

    a_search(transport, FakeClock()).search(QUERY)

    request = transport.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.exa.ai/search"
    assert request.headers["x-api-key"] == SENTINEL_API_KEY
    assert json.loads(request.content) == {
        "query": QUERY,
        "type": "auto",
        "numResults": 5,
        "contents": {"highlights": {"query": QUERY, "maxCharacters": 2000}},
    }


def test_request_times_out_after_thirty_seconds() -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(a_success())

    a_search(transport, FakeClock()).search(QUERY)

    assert transport.requests[0].extensions["timeout"] == {
        "connect": 30.0,
        "read": 30.0,
        "write": 30.0,
        "pool": 30.0,
    }


@pytest.mark.parametrize(
    "url_less_result",
    [
        pytest.param({"title": "Missing url"}, id="missing"),
        pytest.param({"url": None, "title": "Null url"}, id="null"),
        pytest.param({"url": "", "title": "Empty url"}, id="empty"),
    ],
)
def test_result_without_url_is_skipped(url_less_result: dict[str, object]) -> None:
    """# @covers analysis:EXT-014"""
    kept_result = {"url": "https://kept.example.org/", "title": "Kept"}
    transport = ScriptedTransport(
        httpx.Response(200, json={"results": [url_less_result, kept_result]})
    )

    evidence = a_search(transport, FakeClock()).search(QUERY)

    assert [item.url for item in evidence] == ["https://kept.example.org/"]


@pytest.mark.parametrize(
    "sparse_result",
    [
        pytest.param({"url": "https://sparse.example.org/"}, id="missing"),
        pytest.param(
            {
                "url": "https://sparse.example.org/",
                "title": None,
                "publishedDate": None,
                "highlights": None,
            },
            id="null",
        ),
        pytest.param(
            {
                "url": "https://sparse.example.org/",
                "title": 42,
                "publishedDate": 20111018,
                "highlights": "not a list",
            },
            id="wrong-type",
        ),
        pytest.param(
            {"url": "https://sparse.example.org/", "highlights": [7]}, id="non-text-highlight"
        ),
    ],
)
def test_result_without_usable_optional_fields_maps_to_empty_values(
    sparse_result: dict[str, object],
) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(200, json={"results": [sparse_result]}))

    evidence = a_search(transport, FakeClock()).search(QUERY)

    assert evidence == [
        Evidence(url="https://sparse.example.org/", title="", published_date=None, excerpts=())
    ]


@pytest.mark.parametrize(
    "malformed_body",
    [
        pytest.param("<html>gateway error</html>", id="not-json"),
        pytest.param("[]", id="not-an-object"),
        pytest.param('{"results": null}', id="results-not-a-list"),
        pytest.param('{"results": [42]}', id="result-not-an-object"),
    ],
)
def test_malformed_json_yields_no_evidence(malformed_body: str) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(200, text=malformed_body))

    evidence = a_search(transport, FakeClock()).search(QUERY)

    assert evidence == []


@pytest.mark.parametrize("retryable_status_code", [429, 503])
def test_retryable_status_then_success_yields_evidence(retryable_status_code: int) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(retryable_status_code), a_success())

    evidence = a_search(transport, FakeClock()).search(QUERY)

    assert [item.url for item in evidence] == [
        "https://algs4.cs.princeton.edu/22mergesort/",
        "https://stackoverflow.com/questions/7801861/"
        "why-is-merge-sort-worst-case-run-time-o-n-log-n",
    ]


@pytest.mark.parametrize("retryable_status_code", [429, 503])
def test_retryable_status_on_every_attempt_stops_after_three_attempts(
    retryable_status_code: int,
) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(retryable_status_code))

    a_search(transport, FakeClock()).search(QUERY)

    assert len(transport.requests) == 3


@pytest.mark.parametrize("retryable_status_code", [429, 503])
def test_retryable_status_on_every_attempt_yields_no_evidence(
    retryable_status_code: int,
) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(retryable_status_code))

    evidence = a_search(transport, FakeClock()).search(QUERY)

    assert evidence == []


def test_retry_waits_the_retry_after_seconds() -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(429, headers={"Retry-After": "7"}), a_success())
    clock = FakeClock()

    a_search(transport, clock).search(QUERY)

    assert clock.sleeps == [7.0]


@pytest.mark.parametrize(
    "retry_after_headers",
    [
        pytest.param({}, id="absent"),
        pytest.param({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, id="http-date"),
    ],
)
def test_retry_backs_off_one_then_two_seconds_without_numeric_retry_after(
    retry_after_headers: dict[str, str],
) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(503, headers=retry_after_headers))
    clock = FakeClock()

    a_search(transport, clock).search(QUERY)

    assert clock.sleeps == [1.0, 2.0]


def test_consecutive_requests_start_at_least_an_eighth_of_a_second_apart() -> None:
    """# @covers analysis:EXT-014"""
    clock = FakeClock()
    search = a_search(ScriptedTransport(a_success()), clock)

    search.search(QUERY)
    search.search(QUERY)

    assert clock.sleeps == [0.125]


def test_immediate_retry_still_waits_for_its_request_slot() -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(429, headers={"Retry-After": "0"}), a_success())
    clock = FakeClock()

    a_search(transport, clock).search(QUERY)

    assert clock.sleeps == [0.0, 0.125]


@pytest.mark.parametrize("a_failure", NON_RETRYABLE_FAILURES)
def test_non_retryable_failure_yields_no_evidence(
    a_failure: Callable[[], httpx.Response | httpx.HTTPError],
) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(a_failure())

    evidence = a_search(transport, FakeClock()).search(QUERY)

    assert evidence == []


@pytest.mark.parametrize("a_failure", NON_RETRYABLE_FAILURES)
def test_non_retryable_failure_is_attempted_once(
    a_failure: Callable[[], httpx.Response | httpx.HTTPError],
) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(a_failure())

    a_search(transport, FakeClock()).search(QUERY)

    assert len(transport.requests) == 1


@pytest.mark.parametrize("status_code", [401, 403])
def test_rejected_key_raises_credential_error(status_code: int) -> None:
    """# @covers analysis:EXT-014"""
    search = a_search(ScriptedTransport(httpx.Response(status_code)), FakeClock())

    with pytest.raises(SearchCredentialError, match=f"HTTP {status_code}"):
        search.search(QUERY)


def test_exhausted_credits_raise_credits_error() -> None:
    """# @covers analysis:EXT-014"""
    search = a_search(ScriptedTransport(httpx.Response(402)), FakeClock())

    with pytest.raises(SearchCreditsExhaustedError, match="credits are exhausted"):
        search.search(QUERY)


@pytest.mark.parametrize(("status_code", "error_type"), ACCOUNT_ERRORS)
def test_account_error_is_not_retried(status_code: int, error_type: type[Exception]) -> None:
    """# @covers analysis:EXT-014"""
    transport = ScriptedTransport(httpx.Response(status_code))
    search = a_search(transport, FakeClock())

    with pytest.raises(error_type, match=f"HTTP {status_code}"):
        search.search(QUERY)

    assert len(transport.requests) == 1


@pytest.mark.parametrize(("status_code", "error_type"), ACCOUNT_ERRORS)
def test_error_message_never_contains_the_api_key(
    status_code: int, error_type: type[Exception]
) -> None:
    """# @covers analysis:EXT-014"""
    key_echoing_body = {"error": f"request with key {SENTINEL_API_KEY} was rejected"}
    transport = ScriptedTransport(httpx.Response(status_code, json=key_echoing_body))
    search = a_search(transport, FakeClock())

    with pytest.raises(error_type, match=f"HTTP {status_code}") as raised:
        search.search(QUERY)

    assert SENTINEL_API_KEY not in str(raised.value)


@pytest.mark.parametrize(
    "key_echoing_failure",
    [
        pytest.param(
            httpx.LocalProtocolError(f"Illegal header value b'{SENTINEL_API_KEY}\\r'"),
            id="transport-error",
        ),
        pytest.param(
            httpx.Response(200, content=b"\xff" + SENTINEL_API_KEY.encode()),
            id="undecodable-body",
        ),
    ],
)
def test_failure_log_never_contains_the_api_key(
    key_echoing_failure: httpx.Response | httpx.HTTPError, caplog: pytest.LogCaptureFixture
) -> None:
    """# @covers analysis:EXT-014"""
    search = a_search(ScriptedTransport(key_echoing_failure), FakeClock())

    search.search(QUERY)

    assert SENTINEL_API_KEY not in str(vars(caplog.records[0]))
