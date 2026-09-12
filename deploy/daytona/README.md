# Daytona worker snapshot

`build_snapshot.py` bakes the image the konspekt cloud worker runs in: python:3.14-slim, ffmpeg,
tesseract (rus, eng), uv, yt-dlp, deno, Claude Code, the project under `/opt/konspekt`
(`uv sync --frozen --no-dev`, so `/opt/konspekt/.venv/bin/konspekt` is on PATH) and the local Typst
package cache. Resources: 4 vCPU, 8 GiB RAM, 10 GiB disk.

Needs `DAYTONA_API_KEY` (both scripts) and `PROXY_URL` (smoke test) in `.env`, plus Typst packages
in `~/Library/Caches/typst/packages/preview` (compile one konspekt PDF locally first).

    uv run --env-file .env deploy/daytona/build_snapshot.py [--name NAME]
    uv run --env-file .env deploy/daytona/smoke_snapshot.py konspekt-worker-<git short sha>

The default name is `konspekt-worker-<git short sha>`, but the image bakes the working tree, not
the commit. An existing name is refused, so delete the old snapshot or pass `--name`. The smoke
test starts an ephemeral sandbox (proxy on, TTL 20 min), prints tool versions and cgroup limits,
stops at the first failing command with a non-zero exit, and always deletes the sandbox.

# Daytona examiner snapshot

`build_examiner_snapshot.py` bakes the light image the exam examiner runs in: python:3.14-slim,
curl, Claude Code and the project under `/opt/konspekt` installed with `pip install --no-deps`
(the turn command needs only the standard library), so `konspekt-exam-turn` is on PATH. Resources:
1 vCPU, 2 GiB RAM, 5 GiB disk. The control plane creates examiner sandboxes from the snapshot named
in its `EXAMINER_SNAPSHOT` env var; rebuild the snapshot and update the variable together with any
change to the turn protocol.

Needs `DAYTONA_API_KEY` (both scripts) and `CLAUDE_CODE_OAUTH_TOKEN` (smoke test) in `.env`.

    uv run --env-file .env deploy/daytona/build_examiner_snapshot.py [--name NAME]
    uv run --env-file .env deploy/daytona/smoke_examiner_snapshot.py konspekt-examiner-<git short sha> DIR

Naming and the existing-name guard work as for the worker snapshot, with the default name
`konspekt-examiner-<git short sha>`. The smoke test starts an ephemeral sandbox (no proxy, auto-stop
15 min, TTL 20 min), uploads `konspekt.md` and `quiz.json` from `DIR` with an open `turn.json`
into `/root/exam`, runs `konspekt-exam-turn`, prints its output and timings, exits non-zero with
`turn.err` on failure, and always deletes the sandbox.

`deploy/e2e_exam.py [RUN_ID]` checks the deployed exam API end to end (needs `SERVICE_API_KEY`): it
opens an exam on a succeeded run, answers the first question wrong once and every other question
from the quiz key until the session is mastered, and prints each turn's verdict and latency.
