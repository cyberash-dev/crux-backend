# /// script
# requires-python = ">=3.12"
# dependencies = ["daytona==0.211.2"]
# ///
import argparse
import json
import os
import shlex
import time
from pathlib import Path

from daytona import CreateSandboxFromSnapshotParams, Daytona, FileUpload, Sandbox

EXAM_DIR = "/root/exam"
MATERIAL_FILES = ("konspekt.md", "quiz.json")
OPEN_TURN = json.dumps({"kind": "open"})
SANDBOX_AUTO_STOP_MINUTES = 15
SANDBOX_TTL_MINUTES = 20
SANDBOX_CREATE_TIMEOUT_SECONDS = 300
TURN_TIMEOUT_SECONDS = 120
TURN_COMMAND = f"sh -c {shlex.quote(f'konspekt-exam-turn {EXAM_DIR} 2>{EXAM_DIR}/turn.err')}"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test a konspekt examiner snapshot with an open turn in a fresh Daytona sandbox."
    )
    parser.add_argument("snapshot", help="snapshot name, e.g. konspekt-examiner-<git short sha>")
    parser.add_argument("materials", type=Path, help="local directory holding konspekt.md and quiz.json")
    return parser.parse_args()


def oauth_token() -> str:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        raise SystemExit("CLAUDE_CODE_OAUTH_TOKEN is not set")
    return token


def turn_files(materials: Path) -> list[FileUpload]:
    uploads = [
        FileUpload((materials / name).read_bytes(), f"{EXAM_DIR}/{name}") for name in MATERIAL_FILES
    ]
    uploads.append(FileUpload(OPEN_TURN.encode(), f"{EXAM_DIR}/turn.json"))
    return uploads


def run_open_turn(sandbox: Sandbox, uploads: list[FileUpload]) -> None:
    started = time.monotonic()
    sandbox.fs.create_folder(EXAM_DIR, "755")
    sandbox.fs.upload_files(uploads)
    print(f"materials uploaded in {time.monotonic() - started:.1f}s", flush=True)
    started = time.monotonic()
    response = sandbox.process.exec(TURN_COMMAND, timeout=TURN_TIMEOUT_SECONDS)
    print(f"open turn exited {response.exit_code} in {time.monotonic() - started:.1f}s", flush=True)
    print(response.result, flush=True)
    if response.exit_code != 0:
        print(sandbox.process.exec(f"cat {EXAM_DIR}/turn.err").result, flush=True)
        raise SystemExit(f"smoke test failed: konspekt-exam-turn exited with {response.exit_code}")


def main() -> None:
    parsed = arguments()
    uploads = turn_files(parsed.materials)
    started = time.monotonic()
    sandbox = Daytona().create(
        CreateSandboxFromSnapshotParams(
            snapshot=parsed.snapshot,
            env_vars={"CLAUDE_CODE_OAUTH_TOKEN": oauth_token()},
            auto_stop_interval=SANDBOX_AUTO_STOP_MINUTES,
            ttl_minutes=SANDBOX_TTL_MINUTES,
            ephemeral=True,
        ),
        timeout=SANDBOX_CREATE_TIMEOUT_SECONDS,
    )
    print(
        f"sandbox {sandbox.id} started from {parsed.snapshot} in {time.monotonic() - started:.1f}s",
        flush=True,
    )
    try:
        run_open_turn(sandbox, uploads)
    finally:
        sandbox.delete()
        print(f"sandbox {sandbox.id} deleted", flush=True)
    print("smoke test passed")


if __name__ == "__main__":
    main()
