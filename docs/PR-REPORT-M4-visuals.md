# PR report — M4 visuals and structuring (2026-08-22)

Follows docs/PR-REPORT-M3-acceptance.md. Spec change: 14 new records
approved in plan 2026-08-22T141000Z-0sbt9 (delegated per
pipeline:ASM-001); approved contracts extended in place with Deltas
(extraction:DLT-011, analysis:DLT-027/028, output:DLT-033); surfaces
bumped: SUR-010 0.2.0, SUR-020 0.3.0, SUR-030 0.5.0.

## Closed test obligations

| ID | tests (all `@covers`-marked) | oracle summary |
|----|------------------------------|----------------|
| extraction:REQ-011 | tests/features/visual/test_extract_frames.py, tests/pipeline/test_orchestrator.py | fake layout port: valid box reaches capture and artifact; below-min-share / outside-frame / raising port => uncropped, frames still produced |
| extraction:EXT-005 | tests/features/visual/test_claude_cli_layout.py | fake runner: box parsed + budget charged; malformed / runner error => None |
| extraction:DLT-011, CON-012 | tests/features/visual/test_artifact.py | content_box round-trip; old payload without the key parses |
| analysis:CON-022, DLT-027, REQ-026 | tests/features/notes/test_domain_structured_blocks.py, test_artifact.py, test_claude_notes.py | structured blocks round-trip; ragged table / dangling edge / single node / series mismatch rejected; provenance inferred or required |
| analysis:REQ-027, INV-022, ASM-022, DLT-028 | tests/features/notes/test_resolve_illustrations.py, test_compose_notes.py, tests/pipeline/test_orchestrator.py | fakes: commons confirmed => commons figure; unconfirmed => generation with AI label; cap reached / all unconfirmed => dropped, other blocks survive; vision raise => unconfirmed; stored path work-dir-relative |
| analysis:EXT-012 | tests/features/notes/test_wikimedia_commons_search.py | recorded response mapped, svg skipped, non-200 / malformed => empty |
| analysis:EXT-013 | tests/features/notes/test_codex_image_generation.py | stub executable: file produced / non-zero / no file; prompt names the target file |
| analysis:EXT-011 | tests/features/notes/test_claude_cli_vision_check.py | fake runner: matches parsed, budget charged, errors => False |
| output:DLT-033, CON-030 | tests/features/compose/test_structured_markup.py, test_typst_markup.py | table header bold + escaped cells; hierarchy levels / flow chain positions; one bar/plot per series; conditional package imports; generated attribution label |
| output:EXT-021 | tests/features/compose/test_compose_structured_pdf.py | fixture with table + diagrams + charts compiles with pinned fletcher 0.5.8 / lilaq 0.5.0 |
| analysis:INV-020 | tests/features/segmentation/test_snap.py, test_segment_lecture.py | overlaps trimmed on the earlier span, contained spans dropped, speech gaps closed, unlabeled head/tail => admin span |

Suite: 612 tests green; `sdd lint` 0.

## Internal decisions (candidates for Constraint/ASSUMPTION)

- Layout detection runs on 5 full-size probes via `claude -p` + Read;
  the box is validated with Pillow against the first probe's size.
  Cropping is done by ffmpeg `crop=` in both capture passes, so scene
  detection ignores chat/camera changes.
- Figure `provenance` is inferred from `source_ref` prefixes when the
  model omits it (`video ` / `generated:` / `https://`); any other
  source_ref needs an explicit provenance (domain rejects otherwise).
- Illustration request = pseudo-kind `illustration_request` inside the
  section response; only the first is kept; insert position = number of
  preceding real blocks.
- Commons adapter: MediaWiki search API, raster mimes only, 1200 px
  thumb URL, descriptive User-Agent on search AND download
  (upload.wikimedia.org answers 403 to default clients).
- Codex adapter: `codex exec --skip-git-repo-check -s workspace-write -C
  <images_dir>`, stdin closed, 420 s timeout, success = exit 0 and the
  named PNG/JPG exists. Missing binary => logged once, generation off.
- Structured rendering: Typst native `table`; fletcher diagrams with
  Python-computed layout (hierarchy = BFS levels top-down; flow = one row
  up to 4 nodes, otherwise one column); lilaq bar (grouped offsets) and
  line charts; package imports emitted only when such blocks exist.
- Segmentation snap hardening (no spec change, INV-020 intact): overlaps
  resolved in favour of the later start, internal speech gaps closed by
  extending the earlier span, unlabeled head/tail speech becomes an
  `admin` span with a fixed reason so it lands in the cut log.
- `--llm-provider api` path ships `NoLayoutDetection` + `NoVisionCheck`
  (no cropping, no web/generated figures) until API-vision adapters
  exist.

## ASSUMPTIONs used

extraction:ASM-011 (5 probes, 40 % min area), analysis:ASM-022 (1
request/section, 3 Commons candidates, 8 generated/lecture, 3 workers);
review_by 2026-10-15.

## Open-Qs

None raised; analysis:OQ-020 unchanged.

## Acceptance run — Лекция АН-3 (2 h 01 min)

Baseline (pre-M4 code, same transcript/segmentation/factcheck):
11 top-level sections (30 with subsections), 117 prose, 58 definitions,
31 facts, 12 factcheck notes, 8 figures (all video frames, uncropped),
15 deduplicated frames.

M4 run (`--force-from visual`, same upstream artifacts): 11 top-level
sections (35 with subsections), 110 prose, 64 definitions, 28 facts,
10 factcheck notes, 24 figures (13 cropped video frames, 3 Wikimedia
Commons images, 8 generated via Codex; 6 further requests dropped on
the per-lecture generation cap), 22 tables, 19 diagrams, 0 charts;
31 deduplicated frames (15 before cropping: the chat/camera noise no
longer masks slide changes); content_box {x:12, y:130, w:1534, h:885}
on 1920x1080. PDF 55 pages (baseline 35), 12 MB (generated PNGs ~1.3 MB
each). Nominal claude-cli spend 55 USD (subscription), Codex 8 images,
no other external cost.

Visual review after the run drove four compose fixes, all covered by
tests: tall figures capped at 11 cm, diagrams scaled to the page width
with long node labels wrapped, edge labels centered with fill, empty
structured-block captions suppressed and table cells unjustified.

Known gaps for the next round: structured blocks may come without a
caption (schema allows null); Commons captions are written by the
section model, so left/right side wording can disagree with the chosen
plate; generated PNGs are stored at full size (12 MB PDF).

## Addendum — agent-facing Markdown bundle (output:CON-032, pipeline:DLT-003)

`<out>/<slug>/md/`: README.md (metadata, usage note, outline linking
`sections/NN-<section_id>.md`, claims.md, cut-log.md), one file per
top-level section (subsections as level-2 headings with anchors),
definitions/facts/fact-checks as labelled blockquotes, GFM tables,
mermaid `graph TD|LR` diagrams with quoted labels, charts as tables,
images copied into `images/`; the same content flattened into
`<out>/<slug>/konspekt.md` next to the PDF (output:DLT-034, headings
demoted one level, in-file anchors, images under md/images/). Written
at the end of every successful run next to quiz.json; `lecture_status`/`list_lectures` expose
`md_path`. Tests: tests/features/compose/test_markdown_markup.py,
test_export_markdown.py, tests/pipeline/test_orchestrator.py,
test_artifacts_query.py. Labels shared with the PDF renderer via
`compose/application/labels.py`.

## Addendum 2 — source-first illustration selection (analysis:DLT-029, pipeline:DLT-004)

The exact-match vision check favoured generated images (made to the
request's own spec) over verified Commons plates, which is wrong for
precision-sensitive subjects. The check is now a domain-neutral grader
returning a single 0-100 fit score; the verdict is derived from fixed
thresholds (perfect >= 85, suitable >= 50, DLT-030); Commons candidates
(count via --commons-candidates, default 6) are graded in relevance
order with an early stop on the first perfect; generation is disabled
by default and, when enabled via --generated-images, fills only
requests with no perfect Commons candidate and must itself grade
perfect, otherwise the best suitable Commons candidate wins (score,
then search rank). SUR-001 0.3.0. Tests:
tests/features/notes/test_resolve_illustrations.py,
test_claude_cli_vision_check.py, tests/pipeline/test_cli.py.

Verification rerun of the notes stage on lecture 3 with defaults
(generation off, 6 candidates): 16 figures = 13 cropped frames + 3
Commons plates, 0 generated, 18 requests dropped for lack of a
candidate graded at least suitable; tables 23, diagrams 22. A Commons
image picked by both a parent and its subsection surfaced a follow-up
fix: external figures are deduplicated by source_ref across the tree
(first occurrence in outline order wins), applied when storing and
when re-reading the notes artifact.

## Addendum 3 — trust batch (2026-08-25)

Triage of the external improvement handoff (hackathon items rejected;
core kept): model-added verification, ledger precision, quiz v2,
deterministic metrics.

- analysis:REQ-028 + DLT-031 — every fact/definition block carries
  origin (lecture | model_added) and passes the lecturer-claim
  verification pipeline; unsupported model-added facts and disputed
  model-added definitions are dropped, lecture-origin disputes stay
  with an inline warning; every outcome is stored in
  verified_additions and shown in the ledger. Non-prose fields (term,
  captions, table cells, labels) are stripped of literal ** markers.
- analysis:DLT-032 — claims gain claim_id ("c_NNN" positional), the
  verdict "mixed" (same evidence gate as disputed) and corrected_text
  for disputed claims; sources deduplicated.
- analysis:DLT-033 + output:DLT-035 — quiz v2: single_choice /
  multi_select / open with mandatory point-based rubrics; quiz.json
  format_version 2 adds rubric and time_range per question (derived
  from section spans); legacy mcq artifacts migrate by correct-option
  count. SKILL.md gained examiner rules (rubric grading, partial
  credit, targeted follow-up, disputed-claim override).
- output:DLT-036/DLT-037 — PDF cover evidence summary and Markdown
  metrics block built from pipeline/lecture_metrics.py (never by an
  LLM); claims.md orders disputed/mixed first with claim_id /
  rationale / correction columns plus a model-added table.

Surfaces: SUR-020 1.0.0, SUR-030 1.0.0 (breaking quiz type split).

## Debt budget

`unmodeled_budget.current` = 0 in all four partitions (unchanged).
