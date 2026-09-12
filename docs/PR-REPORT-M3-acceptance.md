# PR report — M3 acceptance rounds (2026-08-19..20)

Follows docs/PR-REPORT-M1-M2.md. Gates at every commit point:
`sdd lint` = 0, `sdd ready` = 0, full suite green (419 tests at close).

## What the acceptance rounds delivered

1. **Subscription provider** (pipeline:DLT-001, analysis:EXT-011) — LLM
   stages run through the authenticated Claude Code binary
   (`--llm-provider claude-cli`, default); the direct API path is kept.
2. **Rich markup** (analysis:DLT-020, output:DLT-030) — typed blocks
   (definition/fact callouts, factcheck annotations), inline **term**
   emphasis, justified prose, heading hierarchy.
3. **Quiz export** (analysis:DLT-021, output:CON-031, output:DLT-031) —
   the quiz left the PDF and ships as machine-readable quiz.json with
   multi-correct options and full top-level coverage.
4. **Standalone prose style** (analysis:REQ-025) — no lecture/lecturer
   meta-discourse; single-language output; spacing-safe emphasis.
5. **Hierarchy** (analysis:DLT-022, output:DLT-032) — nested
   subsections (depth 2) in notes and the PDF outline.
6. **Sectioned composition** (analysis:DLT-024, analysis:DLT-025) — the
   outline is planned globally by segmentation (lecture title, nested
   plan, unique ids); notes fan out into independent-context
   per-section requests (4 concurrent, per-section retry, global claim
   indices). Reference lecture comparison (2 h 14 min): 26 → 56 pages,
   definitions 55 → 92, facts 11 → 37, figures 16 → 28, factcheck
   annotations 8 → 27, claims checked 58 → 105.
7. **Live-run hardening** — Opus audio + transport retry
   (extraction:DLT-010), pause-based transcript splitting, silent-gap
   snapping and span clamping (analysis:INV-020 kept intact),
   droppable misplaced figures (analysis:DLT-023), factcheck batching
   (5 claims/request) over 4 workers.
8. **NFR recalibration** (pipeline:DLT-002) — measured reference run
   recorded in docs/nfr-001-probe.md; targets: wall <= 60 min,
   external_api_cost_usd <= 5 (subscription nominal excluded).
9. **Slug transliteration** — Cyrillic file names produce readable
   slugs (`Лекция АН-1.mp4` → `lekciya-an-1`).

## Assumptions still open for review (review_by 2026-10-01)

pipeline:ASM-001 (delegated approvals), extraction:ASM-010 (visual
thresholds), analysis:ASM-020 (web_search-only factcheck),
analysis:ASM-021 (quiz sizing), adapter constants recorded in slice
reports (Scribe splitting thresholds PAUSE 1.2 s / MAX 30 s).

## Debt budget

`unmodeled_budget.current` = 0 in all four partitions.
