# @covers service:CON-002
import json

import httpx
import pytest

from konspekt.worker.adapters.outbound.httpx_worker_api import HttpxWorkerApi
from konspekt.worker.domain.failure_code import FailureCode
from konspekt.worker.domain.file_kind import FileKind
from konspekt.worker.domain.stored_file import StoredFile
from konspekt.worker.ports.outbound.worker_api_error import WorkerApiError

API_BASE = "https://stoic-bird-582.convex.site"
RUN_ID = "k57a1b2c3d4e5f6"
RUN_TOKEN = "run-token-sentinel-8d21fa"
UPLOAD_URL = "https://stoic-bird-582.convex.cloud/api/storage/upload?token=signed-upload"
PDF_BYTES = b"%PDF-1.7 konspekt"


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


class RecordedSleep:
    def __init__(self) -> None:
        self.pauses: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.pauses.append(seconds)


def an_api(transport: ScriptedTransport, sleep: RecordedSleep | None = None) -> HttpxWorkerApi:
    return HttpxWorkerApi(
        api_base=API_BASE,
        run_id=RUN_ID,
        run_token=RUN_TOKEN,
        http_client=httpx.Client(transport=httpx.MockTransport(transport.handler)),
        sleep=sleep or RecordedSleep(),
    )


def accepted() -> httpx.Response:
    return httpx.Response(204)


def an_upload_transport() -> ScriptedTransport:
    return ScriptedTransport(
        httpx.Response(200, json={"upload_url": UPLOAD_URL}),
        httpx.Response(200, json={"storageId": "kg2storage01"}),
    )


def body_of(request: httpx.Request) -> object:
    return json.loads(request.content)


def test_heartbeat_is_posted_to_the_run_events_endpoint() -> None:
    transport = ScriptedTransport(accepted())

    an_api(transport).report_heartbeat()

    assert (str(transport.requests[0].url), body_of(transport.requests[0])) == (
        f"{API_BASE}/worker/runs/{RUN_ID}/events",
        {"type": "heartbeat"},
    )


def test_stage_completed_event_names_the_stage() -> None:
    transport = ScriptedTransport(accepted())

    an_api(transport).report_stage_completed("notes")

    assert body_of(transport.requests[0]) == {"type": "stage_completed", "stage": "notes"}


def test_worker_calls_carry_the_run_token_as_bearer() -> None:
    transport = ScriptedTransport(accepted())

    an_api(transport).report_heartbeat()

    assert transport.requests[0].headers["Authorization"] == f"Bearer {RUN_TOKEN}"


def test_upload_requests_an_upload_url_with_name_type_and_size() -> None:
    transport = an_upload_transport()

    an_api(transport).upload("konspekt.pdf", "application/pdf", PDF_BYTES)

    assert (str(transport.requests[0].url), body_of(transport.requests[0])) == (
        f"{API_BASE}/worker/runs/{RUN_ID}/upload-url",
        {"name": "konspekt.pdf", "content_type": "application/pdf", "size_bytes": len(PDF_BYTES)},
    )


def test_upload_posts_the_bytes_to_the_upload_url_with_their_content_type() -> None:
    transport = an_upload_transport()

    an_api(transport).upload("konspekt.pdf", "application/pdf", PDF_BYTES)

    storage_request = transport.requests[1]
    assert (
        str(storage_request.url),
        storage_request.headers["Content-Type"],
        storage_request.content,
    ) == (UPLOAD_URL, "application/pdf", PDF_BYTES)


def test_upload_never_sends_the_run_token_to_the_storage_url() -> None:
    transport = an_upload_transport()

    an_api(transport).upload("konspekt.pdf", "application/pdf", PDF_BYTES)

    assert "Authorization" not in transport.requests[1].headers


def test_upload_returns_the_storage_id() -> None:
    storage_id = an_api(an_upload_transport()).upload("konspekt.pdf", "application/pdf", PDF_BYTES)

    assert storage_id == "kg2storage01"


def test_upload_url_response_without_upload_url_raises() -> None:
    transport = ScriptedTransport(httpx.Response(200, json={"url": UPLOAD_URL}))

    with pytest.raises(WorkerApiError, match="upload-url response lacks 'upload_url'"):
        an_api(transport).upload("konspekt.pdf", "application/pdf", PDF_BYTES)


def test_oversized_upload_rejection_raises_without_retry() -> None:
    transport = ScriptedTransport(httpx.Response(413))

    with pytest.raises(WorkerApiError, match="upload-url answered HTTP 413"):
        an_api(transport).upload("konspekt.pdf", "application/pdf", PDF_BYTES)

    assert len(transport.requests) == 1


def test_success_completion_posts_result_and_files() -> None:
    transport = ScriptedTransport(accepted())
    result = {"video": {"video_id": "HtSuA80QTyo"}, "sections": [], "llm_spend_usd": 3.5}
    pdf = StoredFile(FileKind.PDF, "konspekt.pdf", "kg2storage01", 17, "application/pdf")

    an_api(transport).complete_succeeded(result, [pdf])

    assert (str(transport.requests[0].url), body_of(transport.requests[0])) == (
        f"{API_BASE}/worker/runs/{RUN_ID}/complete",
        {
            "status": "succeeded",
            "result": result,
            "files": [
                {
                    "kind": "pdf",
                    "name": "konspekt.pdf",
                    "storage_id": "kg2storage01",
                    "size_bytes": 17,
                    "content_type": "application/pdf",
                }
            ],
        },
    )


def test_failed_completion_posts_code_and_message() -> None:
    transport = ScriptedTransport(accepted())

    an_api(transport).complete_failed(FailureCode.PIPELINE_FAILED, "RuntimeError: boom")

    assert body_of(transport.requests[0]) == {
        "status": "failed",
        "error": {"code": "PIPELINE_FAILED", "message": "RuntimeError: boom"},
    }


@pytest.mark.parametrize(
    "status_code",
    [pytest.param(401, id="foreign-token"), pytest.param(409, id="run-already-terminal")],
)
def test_rejected_token_or_terminal_run_raises(status_code: int) -> None:
    transport = ScriptedTransport(httpx.Response(status_code))

    with pytest.raises(WorkerApiError, match=f"events answered HTTP {status_code}"):
        an_api(transport).report_heartbeat()


@pytest.mark.parametrize(
    "status_code",
    [pytest.param(401, id="foreign-token"), pytest.param(409, id="run-already-terminal")],
)
def test_rejected_token_or_terminal_run_is_not_retried(status_code: int) -> None:
    transport = ScriptedTransport(httpx.Response(status_code))
    sleep = RecordedSleep()

    with pytest.raises(WorkerApiError):
        an_api(transport, sleep).report_heartbeat()

    assert (len(transport.requests), sleep.pauses) == (1, [])


def test_server_errors_are_retried_after_2_4_and_8_seconds() -> None:
    transport = ScriptedTransport(
        httpx.Response(503), httpx.Response(502), httpx.Response(500), accepted()
    )
    sleep = RecordedSleep()

    an_api(transport, sleep).report_heartbeat()

    assert sleep.pauses == [2.0, 4.0, 8.0]


def test_network_errors_are_retried() -> None:
    transport = ScriptedTransport(
        httpx.ConnectError("connection refused"), httpx.ReadTimeout("timed out"), accepted()
    )
    sleep = RecordedSleep()

    an_api(transport, sleep).report_heartbeat()

    assert sleep.pauses == [2.0, 4.0]


def test_api_gives_up_after_three_retries() -> None:
    transport = ScriptedTransport(httpx.Response(503))

    with pytest.raises(WorkerApiError, match="events failed after 4 attempts: HTTP 503"):
        an_api(transport).report_heartbeat()

    assert len(transport.requests) == 4


def test_worker_api_error_never_contains_the_run_token() -> None:
    transport = ScriptedTransport(
        httpx.LocalProtocolError(f"Illegal header value b'Bearer {RUN_TOKEN}\\r'")
    )

    with pytest.raises(WorkerApiError, match="LocalProtocolError") as raised:
        an_api(transport).report_heartbeat()

    assert RUN_TOKEN not in str(raised.value)
