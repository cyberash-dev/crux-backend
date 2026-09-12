# PR report — M1+M2 (walking skeleton + all slices + integration)

Commits: `7d840e2` (wave 0), `0237695` (M1+M2), `a3b7f19` (baseline refresh).
Gates: `sdd lint` = 0, `sdd ready` = 0, `sdd check` ok. Tests: 267 passed,
1 skipped (tesseract rus traineddata absent on the dev machine; the OCR
integration test skips with an explicit reason).

## Closed test obligations

Every approved ID of all four partitions carries at least one executable
test with an `@covers` marker; `sdd ready` reports zero uncovered IDs.
Notable oracles:

- `pipeline:REQ-001` — counting-fake producers prove skip-on-fingerprint
  and re-run on config change / foreign schema_version / --force-from.
- `pipeline:POL-001` — sentinel API keys in env; asserts the sentinel is
  absent from every produced file and captured CLI output.
- `pipeline:POL-002` — exhausted budget aborts before the LLM port is
  invoked; earlier artifacts survive.
- `analysis:INV-021` — verdict gate downgrades confirmed/disputed to
  unverified when the source does not resolve (negative oracle:
  fabricated citation must not survive).
- `output:CON-030` / `output:CST-030` — real Typst compilation of a
  bilingual fixture; the test decodes the PDF text layer (ToUnicode
  CMap) and asserts both ru and en probe strings, catching tofu.
- `pipeline:NFR-001` — awaiting_evidence:perf_lab; probe protocol in
  docs/nfr-001-probe.md is pinned by a contract test.

## Internal decisions (candidates for Constraint/ASSUMPTION/Delta)

1. Approved record `output:CON-030` received a syntactic YAML repair
   (quoting three colon-bearing `document_order` items). No field or
   predicate changed; done in place because `sdd record set` refuses
   approved records while the invalid YAML hid the record from the
   covers index. Candidate: patch-level bump note on SUR-030.
2. ElevenLabs Scribe returns ISO 639-3 codes in auto mode; the adapter
   normalizes eng→en, rus→ru (required by CON-011 "BCP-47 primary
   subtag"), unknown codes recorded verbatim per REQ-010.
3. `with_factcheck_sources` (pipeline layer) appends the first claim
   source to factcheck_note text when the notes port omitted it —
   closes the CON-030 "with their source URLs" requirement without
   widening the compose slice input.
4. Budget accounting: adapters charge actual cost after each response
   (usage tokens at claude-opus-5 rates); the orchestrator calls
   `ensure_not_exhausted()` before every LLM stage. Refusals are
   charged (tokens were spent); schema-mismatch retries are charged for
   both attempts.
5. Interval frame sampling uses ffmpeg `select` expressions instead of
   `fps=1/25`: the mjpeg encoder in ffmpeg 8 rejects CFR streams below
   1 fps. Candidate: note on extraction:EXT-002.
6. Tesseract failures of any kind (binary absent, non-zero exit) yield
   `ocr_text: null` and never abort the visual stage. Candidate:
   widening of extraction:EXT-004 error_taxonomy.
7. Typst is invoked with `ignore_system_fonts=True` — determinism per
   output:CST-030 rationale (no host-font fallback).
8. Lecture slug refinement (collapse dashes, `lecture` fallback for
   fully non-Latin names) — recorded in the pipeline Glossary.
9. Typed adapter errors (TranscriptionConfigurationError,
   SegmentationRefusalError, FactcheckResponseError, TypstCompileError,
   MissingFigureImageError, ...) map to exit 1/2 at the CLI boundary.
   Candidate: an error-mapping Contract in a future revision.
10. konspekt.pdf is produced in the work directory by compose and
    copied to `<out>/<slug>/konspekt.pdf` by the orchestrator.

## Assumptions used

- `pipeline:ASM-001` — MVP approvals recorded as approver_identity
  "cyberash" on the user's standing instruction (2026-08-19). review_by
  2026-10-01.
- `extraction:ASM-010` — visual defaults (25 s interval, scene 0.20,
  dHash threshold 10); to be tuned at M3 acceptance.
- `analysis:ASM-020` — factcheck uses web_search only (OQ-020 default).
- `analysis:ASM-021` — quiz size 10 (7 mcq + 3 open), minimum 5.

## Open questions

None blocking. `analysis:OQ-020` resolved by default (option a) into
ASM-020.

## Debt budget

`unmodeled_budget.current` = 0 in all four partitions (greenfield; no
unmodeled behavior introduced; baseline refreshed at `a3b7f19` with all
scope changes traced to approved IDs).
