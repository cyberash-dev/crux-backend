# konspekt

Turns a recorded lecture video (1-2 hours, Russian or English) into a
fact-checked study-notes PDF with a self-check quiz.

What it does:

- transcribes speech with timestamps and speakers (ElevenLabs Scribe v2;
  local faster-whisper as an alternative adapter);
- cuts every off-topic digression, anecdote and admin talk, keeping an
  auditable cut log with reasons;
- fact-checks the lecturer's claims against web sources found through
  the Exa search API (in the lecture language and, for a non-English
  lecture, also in English); a verdict may cite only the sources the
  search returned for that claim. Disagreements
  are marked with a source link and a one-sentence rationale (verdicts
  confirmed / disputed / mixed / unverified, disputed claims carry a
  corrected wording), the lecturer's words are never rewritten;
- audits its own additions: every model-added "interesting fact" or
  definition passes the same verification, unsupported additions are
  dropped, and the full audit lands in the claim ledger;
- extracts deduplicated key frames (slides, whiteboard), cropped to the
  lecture content area (camera tiles and chat are detected once per
  video and cut away), and places them into the relevant sections;
- adds illustrations the recording lacks: Wikimedia Commons candidates
  are graded by a vision check with a 0-100 fit score (>= 85 counts as
  a perfect match, >= 50 as suitable) and the best verified image wins; AI generation (Codex
  `image_gen`, labeled as generated) is off by default and, when
  enabled with `--generated-images`, is used only if no Commons
  candidate is a perfect match;
- turns structured material into tables, hierarchy/flow diagrams and
  bar/line charts next to the prose;
- renders a Typst PDF: title page, table of contents, sections with
  source timecodes, figures with attribution, fact-check annotations,
  typed callouts. Cyrillic fonts are bundled; the quiz ships as
  `quiz.json`;
- resumes cheaply: every stage writes a fingerprinted JSON artifact and
  is skipped when its inputs are unchanged.

## Requirements

- Python >= 3.12, [uv](https://docs.astral.sh/uv/)
- `ffmpeg`/`ffprobe` on PATH
- optional: `tesseract` with `rus`+`eng` traineddata (slide OCR signal)
- optional: `codex` (OpenAI Codex CLI, logged in) for generated
  illustrations; without it only frames and Commons images are used
- network on the first run for the Typst diagram/chart packages
  (`@preview/fletcher`, `@preview/lilaq`, cached afterwards)
- env vars: `ELEVENLABS_API_KEY`, `EXA_API_KEY` (required for every
  build), `ANTHROPIC_API_KEY` (only with `--llm-provider api`)

## Install on another machine

```sh
git clone <repo-url> konspekt && cd konspekt
uv sync
brew install ffmpeg tesseract tesseract-lang   # media + slide OCR (rus)
# Claude Code binary, logged in with your subscription:
#   https://claude.com/claude-code  ->  claude /login
echo 'ELEVENLABS_API_KEY=sk_...' > .env        # transcription key
echo 'EXA_API_KEY=...' >> .env                 # fact-check search key
```

Check the prerequisites at any time: `ffmpeg`, `tesseract` and an
authenticated `claude` on PATH plus the env key are all the pipeline
needs; a missing piece fails fast with exit 2 and an actionable
message.

## Usage

```sh
uv sync
export ELEVENLABS_API_KEY=... EXA_API_KEY=...
uv run konspekt build lecture.mp4 -o out/
```

Output: `out/<lecture-slug>/konspekt.pdf` (for people), `quiz.json`
(machine-readable self-check questions with rubrics and timestamps,
format_version 2), `konspekt.md` (the whole
lecture in one agent-readable Markdown file: outline with anchors,
every section with definitions/facts as blockquotes, tables, mermaid
diagrams and images, fact-check table, cut log) and `md/` (the same
content split per section, `README.md` as entry point); intermediate
artifacts in `out/<lecture-slug>/work/`. The PDF cover, `README.md`
and `konspekt.md` carry a deterministic evidence summary (durations,
coverage ratio, claim and question counts). Useful flags: `--lang auto|ru|en`,
`--force-from <stage>` (invalidate a stage and its tail),
`--max-llm-usd <n>` (spend budget per run, default 15),
`--commons-candidates <n>` (Wikimedia candidates graded per
illustration request, default 6), `--generated-images` (allow AI image
generation when no Commons candidate is graded a perfect match;
disabled by default — without it the best suitable Commons image is
used or the illustration is skipped).

Local transcription instead of the cloud: `uv sync --extra local-whisper`
(adapter selection is wired through `TranscriptionPort`).

## Agent interface

Two ways for coding agents to drive konspekt:

- **Project skill** — `.claude/skills/konspekt/SKILL.md` is picked up
  automatically by Claude Code when working inside this repo: how to
  start builds in the background, map exit codes, poll stage artifacts
  in `out/<slug>/work/`, and read cut log / claims / quiz JSON.
- **MCP server** — for clients outside the repo, register the stdio
  server: `claude mcp add konspekt -- uv run --directory <repo> konspekt-mcp`.
  Tools (`list_lectures`, `lecture_status`, `start_build`, `get_outline`,
  `get_section`, `get_cut_log`, `get_claims`, `get_quiz`) give granular,
  read-only access to results without loading whole artifacts into
  context. Contract: `pipeline:CON-003` in `spec/pipeline.md`.

## Development

Spec-driven: the specification under `spec/` is the source of truth
(`sdd lint` / `sdd ready` gates, see `.sdd/config.json`). Tests:
`uv run pytest`. Architecture: vertical slices with hexagonal ports under
`src/konspekt/features/`, composition root in `src/konspekt/pipeline/`.
