# /// script
# requires-python = ">=3.12"
# dependencies = ["daytona==0.211.2"]
# ///
import argparse
import os
import shlex
from dataclasses import dataclass

from daytona import CreateSandboxFromSnapshotParams, Daytona, Sandbox

SANDBOX_TTL_MINUTES = 20
SANDBOX_CREATE_TIMEOUT_SECONDS = 300
CHECK_TIMEOUT_SECONDS = 120


@dataclass(frozen=True, slots=True)
class Check:
    command: str
    shown_line_count: int | None = None


CHECKS: tuple[Check, ...] = (
    Check("konspekt --help", shown_line_count=5),
    Check("claude --version"),
    Check("yt-dlp --version"),
    Check("deno --version", shown_line_count=1),
    Check("ffmpeg -version", shown_line_count=1),
    Check("tesseract --list-langs"),
    Check("ls /root/.cache/typst/packages/preview"),
    Check("cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max"),
)


def snapshot_name() -> str:
    parser = argparse.ArgumentParser(
        description="Smoke-test a konspekt worker snapshot in a fresh Daytona sandbox."
    )
    parser.add_argument("snapshot", help="snapshot name, e.g. konspekt-worker-<git short sha>")
    name: str = parser.parse_args().snapshot
    return name


def proxy_url() -> str:
    url = os.environ.get("PROXY_URL")
    if not url:
        raise SystemExit("PROXY_URL is not set, expected http://user:pass@host:port")
    return url


def run_check(sandbox: Sandbox, check: Check) -> None:
    response = sandbox.process.exec(
        f"sh -c {shlex.quote(check.command)}", timeout=CHECK_TIMEOUT_SECONDS
    )
    output_lines = response.result.splitlines()
    print(f"$ {check.command}")
    if response.exit_code != 0:
        print("\n".join(output_lines), flush=True)
        raise SystemExit(f"smoke test failed: `{check.command}` exited with {response.exit_code}")
    print("\n".join(output_lines[: check.shown_line_count]), flush=True)


def main() -> None:
    name = snapshot_name()
    sandbox = Daytona().create(
        CreateSandboxFromSnapshotParams(
            snapshot=name,
            outbound_proxy_url=proxy_url(),
            auto_stop_interval=0,
            ttl_minutes=SANDBOX_TTL_MINUTES,
            ephemeral=True,
        ),
        timeout=SANDBOX_CREATE_TIMEOUT_SECONDS,
    )
    print(f"sandbox {sandbox.id} started from {name}", flush=True)
    try:
        for check in CHECKS:
            run_check(sandbox, check)
    finally:
        sandbox.delete()
        print(f"sandbox {sandbox.id} deleted", flush=True)
    print("smoke test passed")


if __name__ == "__main__":
    main()
