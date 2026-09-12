import time
from collections.abc import Callable, Mapping, Sequence

import httpx

from konspekt.worker.domain.failure_code import FailureCode
from konspekt.worker.domain.stored_file import StoredFile
from konspekt.worker.ports.outbound.worker_api_error import WorkerApiError

_RETRY_PAUSES_SECONDS = (2.0, 4.0, 8.0)
_FIRST_SERVER_ERROR_STATUS = 500


class HttpxWorkerApi:
    def __init__(
        self,
        api_base: str,
        run_id: str,
        run_token: str,
        http_client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._run_url = f"{api_base}/worker/runs/{run_id}"
        self._authorization = {"Authorization": f"Bearer {run_token}"}
        self._http_client = http_client
        self._sleep = sleep

    def report_heartbeat(self) -> None:
        self._post_to_run("events", {"type": "heartbeat"})

    def report_stage_completed(self, stage: str) -> None:
        self._post_to_run("events", {"type": "stage_completed", "stage": stage})

    def upload(self, name: str, content_type: str, content: bytes) -> str:
        upload_url_response = self._post_to_run(
            "upload-url", {"name": name, "content_type": content_type, "size_bytes": len(content)}
        )
        upload_url = _response_text(upload_url_response, "upload_url", "upload-url")
        storage_request = self._http_client.build_request(
            "POST", upload_url, headers={"Content-Type": content_type}, content=content
        )
        storage_response = self._response("storage upload", storage_request)
        return _response_text(storage_response, "storageId", "storage upload")

    def complete_succeeded(
        self, result: Mapping[str, object], files: Sequence[StoredFile]
    ) -> None:
        self._post_to_run(
            "complete",
            {
                "status": "succeeded",
                "result": result,
                "files": [_file_body(file) for file in files],
            },
        )

    def complete_failed(self, code: FailureCode, message: str) -> None:
        self._post_to_run(
            "complete", {"status": "failed", "error": {"code": code.value, "message": message}}
        )

    def _post_to_run(self, endpoint: str, body: Mapping[str, object]) -> httpx.Response:
        request = self._http_client.build_request(
            "POST", f"{self._run_url}/{endpoint}", headers=self._authorization, json=body
        )
        return self._response(endpoint, request)

    def _response(self, call_name: str, request: httpx.Request) -> httpx.Response:
        last_failure = ""
        for pause_seconds in (None, *_RETRY_PAUSES_SECONDS):
            if pause_seconds is not None:
                self._sleep(pause_seconds)
            try:
                response = self._http_client.send(request)
            except httpx.TransportError as error:
                last_failure = type(error).__name__
                continue
            if response.status_code < _FIRST_SERVER_ERROR_STATUS:
                return _accepted(call_name, response)
            last_failure = f"HTTP {response.status_code}"
        raise WorkerApiError(
            f"worker API {call_name} failed after {len(_RETRY_PAUSES_SECONDS) + 1} attempts: "
            f"{last_failure}"
        )


def _accepted(call_name: str, response: httpx.Response) -> httpx.Response:
    if not response.is_success:
        raise WorkerApiError(f"worker API {call_name} answered HTTP {response.status_code}")
    return response


def _response_text(response: httpx.Response, field: str, call_name: str) -> str:
    try:
        payload = response.json()
    except ValueError as error:
        raise WorkerApiError(f"worker API {call_name} response is not JSON") from error
    value = payload.get(field) if isinstance(payload, dict) else None
    if not isinstance(value, str) or not value:
        raise WorkerApiError(f"worker API {call_name} response lacks {field!r}")
    return value


def _file_body(file: StoredFile) -> dict[str, object]:
    return {
        "kind": file.kind.value,
        "name": file.name,
        "storage_id": file.storage_id,
        "size_bytes": file.size_bytes,
        "content_type": file.content_type,
    }
