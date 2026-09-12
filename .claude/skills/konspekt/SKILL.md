---
name: konspekt
description: Turn a recorded lecture video into a fact-checked study-notes PDF plus quiz with the konspekt pipeline; start builds, watch pipeline status, and read results (outline, cut log, claims, quiz).
---

# konspekt pipeline operations

## Prerequisites

Fail fast if any is missing (the CLI exits 2 with an actionable message):

- `ELEVENLABS_API_KEY` in the environment or in `.env` at the repo root (cloud transcription, default).
- `EXA_API_KEY` in the environment or in `.env` (fact-check evidence search, required for every build).
- `claude` binary on PATH, logged in (`claude /login`) — default LLM provider `claude-cli`. `ANTHROPIC_API_KEY` is needed only with `--llm-provider api`.
- `ffmpeg`/`ffprobe` on PATH; optional `tesseract` with `rus`+`eng` traineddata (slide OCR signal).

## Start a build

```sh
uv run konspekt build <video> -o out/ [--lang auto|ru|en] [--transcriber elevenlabs|whisper] [--llm-provider claude-cli|api] [--max-llm-usd N] [--force-from <stage>]
```

A 2-hour lecture takes up to ~1 hour. Never block on it: run in the background (`run_in_background`) and poll progress via the artifact files below. Full CLI contract: `spec/pipeline.md` (`pipeline:CON-001`).

Exit codes:

- `0` — success, PDF on disk.
- `1` — runtime failure: external API error, transcription network failure after retry, or LLM budget exceeded (`BUDGET_EXCEEDED`, cap set by `--max-llm-usd`, default 15). Completed stage artifacts stay on disk; re-run to resume.
- `2` — invalid invocation or configuration: missing video, unknown flag, missing credential for a selected adapter, `claude` binary absent. No stage executed.

## Read status

`out/<slug>/work/` fills with one JSON per completed stage, in order:

```
01-ingest.json  02-transcription.json  03-visual.json  04-segmentation.json
05-factcheck.json  06-notes.json  07-quiz.json  08-compose.json
```

`<slug>` is a transliteration of the video file name. The highest `NN` present = last completed stage. Each file is an envelope `{schema_version, stage, input_fingerprint, created_at, payload}` (`pipeline:CON-002`); stage content lives under `payload`.

Results: `out/<slug>/konspekt.pdf` (for people), `out/<slug>/quiz.json` (export shape: `output:CON-031`) and the agent-facing Markdown (`output:CON-032`): `out/<slug>/konspekt.md` holds the whole lecture in one file (outline with anchors, every section with definitions/facts as blockquotes, GFM tables, mermaid diagrams, images under `md/images/`, then the fact-check table and the cut log); `out/<slug>/md/` is the same content split per section (`md/README.md` entry point, `md/sections/NN-<section_id>.md`, `md/claims.md`, `md/cut-log.md`). To learn a lecture and answer questions about it, read `konspekt.md` rather than the PDF.

## Checkpoints and re-runs

Stages are fingerprinted: an unchanged stage is skipped on re-run, so re-running after a failure resumes from the first missing/stale artifact. `--force-from <stage>` invalidates that stage AND every stage after it (the tail re-runs; earlier artifacts are kept). Stage names are the eight listed above.

## Read results from artifacts

Read only the fields you need; full schemas live in `spec/*.md` — do not guess beyond them.

- Cut log: `work/04-segmentation.json` → `payload.spans[]` with `start_seconds`, `end_seconds`, `label` (`core|tangent|anecdote|admin`), `reason` (non-core only). Schema: `analysis:CON-020` in `spec/analysis.md`.
- Claims: `work/05-factcheck.json` → `payload.claims[]` with `claim_id`, `claim_text`, `verdict` (`confirmed|disputed|mixed|unverified`), `sources[]`, `annotation` (rationale for disputed/mixed), `corrected_text` (disputed only). Schema: `analysis:CON-021`. Model-added facts/definitions are audited separately in `work/06-notes.json` → `payload.verified_additions[]` and in `md/claims.md`.
- Quiz: `work/07-quiz.json` → `payload.questions[]` with `prompt`, `type` (`single_choice|multi_select|open`), `options`, `correct_options`, `model_answer`, `rubric`, `section_id`; or the standalone export `out/<slug>/quiz.json` (format_version 2, adds `time_range` and `section_title`). Schemas: `analysis:CON-023`, `output:CON-031`.
- Outline/notes: `work/04-segmentation.json` → `payload.sections_plan[]`, `work/06-notes.json` (`analysis:CON-022`).

## Examining a learner with quiz.json

`quiz.json` (format_version 2) is built for an agent examiner. Rules:

- `single_choice` — exactly one correct index; `multi_select` — two or
  more (award full credit only for the exact set; partial credit =
  hits minus false picks, floored at 0, over the correct count).
- `open` — grade against `rubric.concepts`, NOT by similarity to
  `model_answer`: award each concept's `points` when the answer
  expresses it (any wording); sum; `max_points` is the ceiling.
  `model_answer` is a reference formulation for feedback.
- Give partial credit and name the missing concepts; ask ONE targeted
  follow-up about a missing concept before revealing anything.
- After the attempts, point the learner to the source: `time_range`
  (seconds into the lecture video) and `section_id` → the matching
  `md/sections/*.md` file.
- Check `md/claims.md` first: if a related lecture claim is disputed or
  mixed, grade against the corrected/annotated statement and say so
  explicitly.

## Typical failures

- Exit 2, message names `ELEVENLABS_API_KEY` → key missing/invalid; put it in `.env`.
- Exit 2, message names `EXA_API_KEY` → key missing, or Exa rejected it mid-run (HTTP 401/403); fix it in `.env` and re-run (completed stages are reused).
- Exit 1 with `BUDGET_EXCEEDED` → raise `--max-llm-usd` and re-run (completed stages are reused).
- Exit 1 on transcription network errors → the adapter already retried once; just re-run (resumes at transcription).
- `faster-whisper is not installed` → `uv sync --extra local-whisper` or drop `--transcriber whisper`.

## MCP variant

For external clients or granular reads without loading whole artifacts into context, register the MCP server:

```sh
claude mcp add konspekt -- uv run --directory <repo> konspekt-mcp
```

Tools: `list_lectures`, `lecture_status`, `start_build` (detached; poll `lecture_status`), `get_outline`, `get_section`, `get_cut_log`, `get_claims`, `get_quiz`. Contract: `pipeline:CON-003` in `spec/pipeline.md`. Prefer MCP when you need one section or a filtered claim list — `get_section`/`get_claims` return just that slice instead of a multi-megabyte artifact. Working inside this repo with the CLI available, reading `work/*.json` directly is fine too.
