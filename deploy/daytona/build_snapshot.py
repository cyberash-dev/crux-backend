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
PROJECT_FILES = ("pyproject.toml", "uv.lock", "README.md", ".python-version")
LOCAL_TYPST_PACKAGES = Path.home() / "Library/Caches/typst/packages/preview"
SANDBOX_TYPST_PACKAGES = "/root/.cache/typst/packages/preview"
APT_INSTALL = (
    "apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr "
    "tesseract-ocr-rus tesseract-ocr-eng curl ca-certificates "
    "&& rm -rf /var/lib/apt/lists/*"
)
PIP_TOOLS = ("uv==0.10.2", "yt-dlp[default]==2026.8.19", "deno==2.9.6")
CLAUDE_CODE_INSTALL = (
    "curl -fsSL -o /tmp/claude-install.sh https://claude.ai/install.sh "
    "&& bash /tmp/claude-install.sh"
)
PROJECT_INSTALL = "uv sync --frozen --no-dev"
SANDBOX_PATH = ":".join(
    (
        f"{PROJECT_DIR}/.venv/bin",
        "/root/.local/bin",
        "/usr/local/sbin",
        "/usr/local/bin",
        "/usr/sbin",
        "/usr/bin",
        "/sbin",
        "/bin",
    )
)
SNAPSHOT_RESOURCES = Resources(cpu=4, memory=8, disk=10)


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
        description="Build the Daytona snapshot the konspekt cloud worker runs in."
    )
    parser.add_argument("--name", help="snapshot name (default: konspekt-worker-<git short sha>)")
    requested_name: str | None = parser.parse_args().name
    return requested_name or f"konspekt-worker-{head_short_sha()}"


def worker_image() -> Image:
    image = (
        Image.base(BASE_IMAGE)
        .run_commands(APT_INSTALL)
        .pip_install(*PIP_TOOLS, extra_options="--no-cache-dir")
        .run_commands(CLAUDE_CODE_INSTALL)
        .add_local_dir(LOCAL_TYPST_PACKAGES, SANDBOX_TYPST_PACKAGES)
    )
    for project_file in PROJECT_FILES:
        image = image.add_local_file(REPO_ROOT / project_file, f"{PROJECT_DIR}/{project_file}")
    return (
        image.add_local_dir(REPO_ROOT / "src", f"{PROJECT_DIR}/src")
        .workdir(PROJECT_DIR)
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
        CreateSnapshotParams(name=name, image=worker_image(), resources=SNAPSHOT_RESOURCES),
        on_logs=print_build_log,
    )
    print(f"snapshot built in {time.monotonic() - started:.0f}s", flush=True)
    print(name)


if __name__ == "__main__":
    main()
