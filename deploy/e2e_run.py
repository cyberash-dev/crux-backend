# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28"]
# ///
import os
import sys
import time

import httpx

DEFAULT_API_BASE = "https://stoic-bird-582.eu-west-1.convex.site"
DEFAULT_VIDEO_URL = "https://www.youtube.com/watch?v=ZA-tUyM_y7s"
POLL_INTERVAL_SECONDS = 20
TIMEOUT_MINUTES = 150
TERMINAL_STATUSES = frozenset({"succeeded", "failed"})


def submitted_run_id(client: httpx.Client, video_url: str) -> str:
    response = client.post("/v1/runs", json={"youtube_url": video_url, "lang": "auto"})
    print(f"POST /v1/runs -> {response.status_code} {response.text}")
    response.raise_for_status()
    return str(response.json()["run_id"])


def final_status(client: httpx.Client, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + TIMEOUT_MINUTES * 60
    reported_stages: set[str] = set()
    while time.monotonic() < deadline:
        status = client.get(f"/v1/runs/{run_id}").json()
        for stage in status.get("stages", []):
            if stage["name"] not in reported_stages:
                reported_stages.add(stage["name"])
                print(f"  stage {stage['name']:<14} {stage['completed_at']}")
        if status["status"] in TERMINAL_STATUSES:
            return status
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"run {run_id} not finished after {TIMEOUT_MINUTES} minutes")


def print_result_summary(client: httpx.Client, run_id: str) -> None:
    result = client.get(f"/v1/runs/{run_id}/result").json()
    print(f"video: {result['video']}")
    print(f"sections: {len(result['sections'])}, claims: {len(result['claims'])}")
    print(f"quiz questions: {len(result['quiz'].get('questions', []))}")
    for file in result["files"]:
        print(f"  {file['kind']:<8} {file['name']:<40} {file['size_bytes']:>9} B")


def main() -> int:
    api_key = os.environ.get("SERVICE_API_KEY")
    if not api_key:
        print("SERVICE_API_KEY is not set", file=sys.stderr)
        return 2
    video_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIDEO_URL
    api_base = os.environ.get("KONSPEKT_SERVICE_URL", DEFAULT_API_BASE)
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(base_url=api_base, headers=headers, timeout=30) as client:
        run_id = submitted_run_id(client, video_url)
        status = final_status(client, run_id)
        print(f"run {run_id}: {status['status']} error={status.get('error')} "
              f"llm_spend_usd={status.get('llm_spend_usd')}")
        if status["status"] != "succeeded":
            return 1
        print_result_summary(client, run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
