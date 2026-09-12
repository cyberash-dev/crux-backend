# /// script
# requires-python = ">=3.12"
# dependencies = ["daytona==0.211.2"]
# ///
import argparse
import subprocess
import time
from pathlib import Path

from daytona import CreateSnapshotParams, Daytona, DaytonaNotFoundError, Image, Resources

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_IMAGE = "python:3.14-slim"
PROJECT_DIR = "/opt/konspekt"
PROJECT_FILES = ("pyproject.toml", "README.md")
APT_INSTALL = (
    "apt-get update && apt-get install -y --no-install-recommends curl ca-certificates "
    "&& rm -rf /var/lib/apt/lists/*"
)
CLAUDE_CODE_INSTALL = (
    "curl -fsSL -o /tmp/claude-install.sh https://claude.ai/install.sh "
    "&& bash /tmp/claude-install.sh"
)
PROJECT_INSTALL = f"pip install --no-cache-dir --no-deps {PROJECT_DIR}"
SANDBOX_PATH = "/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SNAPSHOT_RESOURCES = Resources(cpu=1, memory=2, disk=5)


def head_short_sha() -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "--short", "HEAD"),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def snapshot_name() -> str:
    parser = argparse.ArgumentParser(
        description="Build the Daytona snapshot the konspekt exam examiner runs in."
    )
    parser.add_argument("--name", help="snapshot name (default: konspekt-examiner-<git short sha>)")
    requested_name: str | None = parser.parse_args().name
    return requested_name or f"konspekt-examiner-{head_short_sha()}"


def examiner_image() -> Image:
    image = Image.base(BASE_IMAGE).run_commands(APT_INSTALL).run_commands(CLAUDE_CODE_INSTALL)
    for project_file in PROJECT_FILES:
        image = image.add_local_file(REPO_ROOT / project_file, f"{PROJECT_DIR}/{project_file}")
    return (
        image.add_local_dir(REPO_ROOT / "src", f"{PROJECT_DIR}/src")
        .run_commands(PROJECT_INSTALL)
        .env({"PATH": SANDBOX_PATH})
    )


def reject_existing_snapshot(daytona: Daytona, name: str) -> None:
    try:
        existing = daytona.snapshot.get(name)
    except DaytonaNotFoundError:
        return
    raise SystemExit(
        f"snapshot {name} already exists (state {existing.state.value}); "
        "delete it first or pass another --name"
    )


def print_build_log(line: str) -> None:
    print(line, flush=True)


def main() -> None:
    name = snapshot_name()
    daytona = Daytona()
    reject_existing_snapshot(daytona, name)
    started = time.monotonic()
    daytona.snapshot.create(
        CreateSnapshotParams(name=name, image=examiner_image(), resources=SNAPSHOT_RESOURCES),
        on_logs=print_build_log,
    )
    print(f"snapshot built in {time.monotonic() - started:.0f}s", flush=True)
    print(name)


if __name__ == "__main__":
    main()
