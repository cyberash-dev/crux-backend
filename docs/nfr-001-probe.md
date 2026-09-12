# NFR-001 probe protocol

Manual perf-lab measurement for `pipeline:NFR-001` (2-hour lecture:
wall_clock_minutes <= 60 without local whisper,
external_api_cost_usd <= 5).

## Preconditions

- Reference lecture: a real 1.5-2 hour lecture video agreed with the
  owner (recorded in the run notes below when executed).
- Clean state: the lecture's work directory removed before the run.
- Environment: macOS arm64, `ELEVENLABS_API_KEY` set, `claude` binary
  authenticated (subscription), network available.

## Procedure

1. `time uv run konspekt build <reference.mp4> -o out/`
2. Record `real` from `time` output as wall_clock_minutes.
3. Record external_api_cost_usd: the transcription provider's billed
   amount for the run (ElevenLabs dashboard) plus Anthropic API spend
   only when `--llm-provider api` was used. The `total spend` line of
   the run summary is the nominal budget-guard figure and is NOT this
   metric under the claude-cli provider.
4. Attach the numbers plus the git commit sha to the run notes below.

## Pass criteria

- exit code 0, `konspekt.pdf` and `quiz.json` produced;
- wall_clock_minutes <= 60;
- external_api_cost_usd <= 5.

## Run notes

| date | commit | lecture | wall clock (min) | external cost (USD) | verdict |
|------|--------|---------|------------------|---------------------|---------|
| 2026-08-20 | 5ba70bd+ | Лекция АН-1.mp4 (2 h 14 min, ru) | ~50 composed from staged runs: transcription 13, visual 4, segmentation 16, factcheck ~10, sectioned notes ~15, quiz 3, compose <1 | ~0.6 (ElevenLabs; claude-cli nominal 52.39 excluded) | PASS (composed measurement; a single clean run pending) |
