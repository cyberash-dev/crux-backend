import os
import sys
from collections.abc import Mapping
from pathlib import Path

import httpx

from konspekt.worker.adapters.outbound.httpx_worker_api import HttpxWorkerApi
from konspekt.worker.adapters.outbound.konspekt_build_runner import KonspektBuildRunner
from konspekt.worker.adapters.outbound.system_clock import SystemClock
from konspekt.worker.adapters.outbound.yt_dlp_video_source import YtDlpVideoSource
from konspekt.worker.application.run_request import RunRequest
from konspekt.worker.application.worker_run import WorkerRun
from konspekt.worker.domain.secret_values import SecretValues
from konspekt.worker.ports.outbound.worker_api_error import WorkerApiError

_DEFAULT_WORK_DIR = "/root/konspekt-run"
_DEFAULT_MAX_LLM_USD = "60"
_REQUIRED_ENV_NAMES = (
    "KONSPEKT_RUN_ID",
    "KONSPEKT_API_BASE",
    "KONSPEKT_RUN_TOKEN",
    "KONSPEKT_YOUTUBE_URL",
    "KONSPEKT_LANG",
)
_SECRET_ENV_NAMES = (
    "KONSPEKT_RUN_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ELEVENLABS_API_KEY",
    "EXA_API_KEY",
    "HTTPS_PROXY",
    "PROXY_URL",
    "DAYTONA_API_KEY",
    "SERVICE_API_KEY",
)
_HTTP_TIMEOUT_SECONDS = 60.0
_INVALID_ENVIRONMENT_EXIT_CODE = 2
_WORKER_STOPPED_EXIT_CODE = 1


def main() -> None:
    sys.exit(run_worker(os.environ))


def run_worker(environment: Mapping[str, str]) -> int:
    missing_names = [name for name in _REQUIRED_ENV_NAMES if not environment.get(name)]
    if missing_names:
        print(f"error: missing required env vars: {', '.join(missing_names)}", file=sys.stderr)
        return _INVALID_ENVIRONMENT_EXIT_CODE
    try:
        max_llm_usd = float(environment.get("KONSPEKT_MAX_LLM_USD", _DEFAULT_MAX_LLM_USD))
    except ValueError:
        print("error: KONSPEKT_MAX_LLM_USD must be a number", file=sys.stderr)
        return _INVALID_ENVIRONMENT_EXIT_CODE
    work_dir = Path(environment.get("KONSPEKT_WORK_DIR", _DEFAULT_WORK_DIR))
    work_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS) as http_client:
        try:
            _worker_run(environment, work_dir, max_llm_usd, http_client).execute()
        except WorkerApiError as error:
            print(f"error: {error}", file=sys.stderr)
            return _WORKER_STOPPED_EXIT_CODE
    return 0


def _worker_run(
    environment: Mapping[str, str], work_dir: Path, max_llm_usd: float, http_client: httpx.Client
) -> WorkerRun:
    clock = SystemClock()
    return WorkerRun(
        video_source=YtDlpVideoSource(proxy_url=environment.get("HTTPS_PROXY")),
        build_runner=KonspektBuildRunner(log_dir=work_dir),
        worker_api=HttpxWorkerApi(
            api_base=environment["KONSPEKT_API_BASE"],
            run_id=environment["KONSPEKT_RUN_ID"],
            run_token=environment["KONSPEKT_RUN_TOKEN"],
            http_client=http_client,
            sleep=clock.sleep,
        ),
        clock=clock,
        secret_values=SecretValues(environment.get(name, "") for name in _SECRET_ENV_NAMES),
        request=RunRequest(
            youtube_url=environment["KONSPEKT_YOUTUBE_URL"],
            language=environment["KONSPEKT_LANG"],
            work_dir=work_dir,
            max_llm_usd=max_llm_usd,
        ),
    )
