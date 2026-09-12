# `konspekt` — Partition `analysis`

> LLM analysis: topic segmentation with tangent cutting, claim
> fact-checking, notes generation with media, self-check quiz.

---

## 1. Context

The analysis partition owns pipeline stages 4-7. `segmentation` builds a
global section plan over the whole transcript, then labels every
transcript span as core content or cut material, producing an auditable
cut log. `factcheck` extracts verifiable claims from core content and
verifies them against web sources; disagreements are marked, never
rewritten. `notes` composes the study-notes structure with prose,
figures selected from extracted frames (or external images), and
fact-check marks. `quiz` generates self-check questions bound to note
sections. All four stages call the Anthropic API through ports; tests
use fakes.

## 2. Glossary

- **Span** — a half-open time interval [start_seconds, end_seconds) of
  the lecture timeline referencing consecutive transcript segments.
- **Span label** — one of `core` (on-topic teaching content), `tangent`
  (off-topic digression), `anecdote` (story/joke without teaching
  content), `admin` (organizational talk: attendance, exams, breaks).
- **Cut log** — the list of all non-core spans with their labels and a
  one-sentence reason each.
- **Claim** — a factual statement extracted from core content that an
  external source can confirm or dispute.
- **Verdict** — one of `confirmed`, `disputed`, `unverified`.
- **Resolvable source** — an HTTPS URL or DOI that answered with HTTP
  status < 400 to a HEAD or GET request at fact-check time.
- **Section** — one unit of the notes document with a title, prose
  blocks, figures, and the source span references.

## 3. Partition

```yaml
---
id: analysis
type: Partition
partition_id: analysis
owner_team: cyberash
gate_scope:
  - analysis
dependencies_on_other_partitions:
  - pipeline:SUR-002@0.1.0
  - extraction:SUR-010@0.1.0
  - pipeline:POL-001@1
  - pipeline:POL-002@1
default_policy_set:
  - pipeline:POL-001
  - pipeline:POL-002
id_namespace: analysis
unmodeled_budget:
  current: 0
  baseline_at: "2026-08-19"
  baseline_value: 0
  trend: monotonic_non_increasing
---
```

## 4. Brownfield baseline

None. Greenfield repository; the single baseline record is
`pipeline:BL-001` in `spec/pipeline.md`.

## 5. Surfaces

```yaml
---
id: analysis:SUR-020
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
name: konspekt/analysis-artifacts
version: "2.0.0"
boundary_type: public_storage
members:
  - analysis:CON-020
  - analysis:CON-021
  - analysis:CON-022
  - analysis:CON-023
consumer_compat_policy: semver_per_surface
notes: |
  v2.0.0 — breaking: sources of confirmed, disputed and mixed claims
  are URLs of the claim's search evidence (analysis:INV-021 via
  analysis:DLT-035); verification is evidence-first (analysis:DLT-034).
  v1.0.0 — breaking: quiz question types split into
  single_choice/multi_select with mandatory open-question rubrics
  (DLT-033); additive: claim_id/mixed/corrected_text on claims
  (DLT-032), origin and verified_additions on notes (DLT-031).
  v0.3.0 — additive: structured blocks (table, diagram, chart) and
  figure provenance in notes.json (analysis:DLT-027).
---
```

## 6. Requirements

```yaml
---
id: analysis:REQ-020
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: every transcript span is labeled; only core reaches the notes
given: |
  - a transcript artifact (extraction:CON-011) with at least one segment
when: the segmentation stage runs
then: |
  the segments artifact (analysis:CON-020) contains a set of labeled
  spans that covers the transcript timeline per analysis:INV-020; every
  span carries exactly one label from {core, tangent, anecdote, admin};
  downstream, the notes stage receives only the text of core spans —
  text of non-core spans is absent from notes prose.
negative_cases:
  - an empty transcript => the stage fails with a typed error, run exits 1
  - the labeling port returns spans not covering the timeline => the
    stage fails with a typed error naming the first gap
out_of_scope:
  - editing or summarizing the audio/video itself
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    With a fake labeling port, every stored span carries one valid
    label; a fixture where the fake returns a gap raises the typed
    error; notes built from the result contain no substring unique to
    the non-core spans of the fixture.
  test_template: unit
  boundary_classes:
    - full coverage labeling
    - gap in coverage => typed error
    - non-core text excluded from notes input
  failure_scenarios:
    - tangent text silently reaching the notes
---
```

```yaml
---
id: analysis:REQ-022
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: fact-check marks disagreements without rewriting the lecturer
given: |
  - core spans with extracted claims
  - an evidence search (analysis:EXT-014) returning, per claim and
    search language, sources with query-focused excerpts
  - a verification port grading a batch of claims against their
    numbered evidence
when: the factcheck stage runs and the notes stage renders its output
then: |
  every claim is searched in the lecture language and, when the lecture
  language is not English, also in English (the English queries come
  from one translation request per batch); the verification port
  grades each claim only against its own evidence and cites evidence
  by number, never by a free-form URL; the stored sources are the URLs
  of the cited evidence (analysis:INV-021). Each claim in the claims
  artifact (analysis:CON-021) keeps the lecturer's statement verbatim
  as claim_text; in the notes, a disputed claim is rendered as the
  lecturer's original statement plus a marked annotation citing the
  source — the original statement text is never replaced or corrected
  in place.
negative_cases:
  - verification port returns "disputed" without citing evidence, or
    cites a number outside the claim's evidence => the claim is stored
    as "unverified" and the discrepancy annotation is omitted
  - the evidence search fails or returns nothing for a claim => the
    claim is stored as "unverified"
out_of_scope:
  - exhaustive verification of every sentence; only extracted claims are
    checked
  - publishing search excerpts; they are model input only
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    With fake search and verification ports: a claim disputed with a
    cited evidence number is stored with that evidence URL, claim_text
    byte-identical to the input statement and the annotation; a
    citation outside the claim's evidence and an empty search result
    both yield "unverified"; a non-English lecture searches every claim
    in the lecture language and in English, an English lecture only in
    English.
  test_template: unit
  boundary_classes:
    - disputed with cited evidence
    - confirmed with cited evidence
    - citation outside the evidence => unverified
    - empty evidence => unverified
    - non-English lecture searched in two languages
  failure_scenarios:
    - claim_text mutated by the pipeline
    - a URL invented by the model reaching the artifact
---
```

```yaml
---
id: analysis:REQ-023
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: self-check quiz bound to note sections
given: |
  - a notes artifact (analysis:CON-022) with at least three sections
when: the quiz stage runs
then: |
  the quiz artifact (analysis:CON-023) covers the whole material: every
  TOP-LEVEL section of the notes artifact is referenced by at least one
  question (a question referencing a subsection credits its top-level
  parent), and the total question count is at least
  max(10, 2 x top-level section count); each question has type "mcq"
  (exactly four options, one or more correct) or "open" (model answer
  text); each question's section_id resolves to an existing section or
  subsection of the notes artifact.
negative_cases:
  - a question referencing a non-existent section_id => the stage fails
    with a typed error
  - a notes section with zero questions => the stage fails with a typed
    error naming the uncovered section
out_of_scope:
  - adaptive difficulty, spaced repetition scheduling
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    With a fake quiz port, stored questions satisfy the coverage rule
    (every section referenced, total >= max(10, 2 x sections)), the mcq
    shape (4 options, >= 1 correct), and section_id resolution; a fake
    leaving one section uncovered raises the typed error naming it; a
    fake returning a dangling section_id raises the typed error.
  test_template: unit
  boundary_classes:
    - full coverage met
    - uncovered section => typed error
    - mcq shape valid incl. multi-correct
    - dangling section_id => typed error
  failure_scenarios:
    - quiz shipped with an unanswerable or unresolvable question
---
```

```yaml
---
id: analysis:REQ-024
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: section media carry source attribution
given: |
  - a frames artifact (extraction:CON-012) and note sections under
    construction
when: the notes stage attaches figures to sections
then: |
  every figure in the notes artifact carries a source_ref and a
  provenance: for a video frame — the frame timestamp label
  ("video HH:MM:SS", provenance video_frame); for a Wikimedia Commons
  image — the HTTPS file page URL (provenance commons); for a generated
  image — "generated:codex" (provenance generated). A figure without
  source_ref fails validation of analysis:CON-022. Frame figures
  reference frames whose timestamp lies inside the section's source
  spans. Commons and generated figures enter the notes only through the
  illustration resolver (analysis:REQ-027).
negative_cases:
  - external image that failed to download => the figure is dropped
    and the drop is recorded in the run log; the run continues
  - frame figure whose timestamp lies outside the section source spans
    => the figure is dropped and the drop is recorded in the run log;
    the run continues (a misplaced illustration never discards the
    composed notes)
out_of_scope:
  - copyright clearance of external images (the source URL is cited;
    usage rights stay the user's responsibility)
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    Serde rejects a figure without source_ref; a frame figure whose
    timestamp is outside the section spans is dropped from the composed
    notes while every other block survives; a failed external download
    results in a notes artifact without that figure and the run
    continuing.
  test_template: unit
  boundary_classes:
    - frame figure inside span
    - frame figure outside span => dropped, other blocks survive
    - figure without source_ref => rejected
    - failed download => dropped, run continues
  failure_scenarios:
    - unattributed image reaching the PDF
---
```

```yaml
---
id: analysis:REQ-025
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T21:44:33.239Z
    change_request: "acceptance feedback round 2: standalone prose style, quiz leaves the PDF (user, 2026-08-19)"
    scope: first-time-approval
partition_id: analysis
title: notes prose is standalone educational text
given: |
  - core spans, claims and frames as inputs of the notes stage
when: the notes stage composes section content
then: |
  the prose reads as a self-contained study text on the subject matter:
  no references to the lecture, the lecturer, the recording, the
  platform, or the audience ("лекция открывается", "лектор
  подчёркивает", "как сказано на слайде" are all excluded); statements
  are written directly ("Анатомия изучает ..."), in the lecture
  language; inline **term** emphasis wraps the term only and preserves
  the surrounding spacing; the text contains only characters plausible
  for the lecture language plus Latin scientific terms.
negative_cases:
  - meta-discourse about the lecture or lecturer in prose => acceptance
    defect, prompt-level regression
out_of_scope:
  - figure source_ref attribution lines (they keep referencing the
    video timestamp per analysis:REQ-024)
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    The notes composition prompt (shared by the api and cli adapters)
    instructs: standalone study text, direct statements, the exclusion
    of lecture/lecturer/platform meta-discourse, emphasis wrapping the
    term only with preserved spacing, and single-language output
    without stray foreign characters. Verified by unit tests on the
    prompt text; the rendered result is manually accepted on the
    reference lectures.
  test_template: unit
  boundary_classes:
    - prompt carries every instruction listed
  failure_scenarios:
    - meta-discourse reaching the PDF
---
```

```yaml
---
id: analysis:REQ-026
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.026Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
title: structured material is rendered as tables, diagrams and charts
given: |
  - a section under composition whose core text carries structured
    material: classifications and hierarchies, comparisons of several
    items along the same properties, ordered processes or sequences,
    numeric series
when: the notes stage composes the section
then: |
  the section carries, in addition to its prose, typed structured
  blocks per analysis:CON-022: a table block (columns + rows) for
  comparisons and property matrices; a diagram block of kind hierarchy
  for classifications and of kind flow for ordered processes; a chart
  block of kind bar or line for numeric series. Structured blocks are
  self-contained data (no markup), carry a caption, and their data
  satisfy the CON-022 postconditions (row length equals column count,
  edges reference declared node ids, series length equals category
  count); a section without structured material carries no structured
  blocks.
negative_cases:
  - a structured block violating the CON-022 data postconditions =>
    the section response is rejected and re-requested once, then the
    stage fails (same rule as other malformed section responses)
  - an empty table, a diagram with fewer than two nodes, or a chart
    without series => rejected as above
out_of_scope:
  - free-form drawings; spatial/anatomical pictures are figures
    (analysis:REQ-024, analysis:REQ-027), not diagrams
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    Section responses carrying valid table, diagram and chart blocks
    parse into the corresponding blocks; responses with a ragged table,
    a dangling diagram edge, a single-node diagram or a series whose
    length differs from the categories are rejected with a typed error.
  test_template: unit
  boundary_classes:
    - valid table, hierarchy diagram, flow diagram, bar chart, line chart
    - ragged table => rejected
    - dangling edge => rejected
    - single-node diagram => rejected
    - series/category length mismatch => rejected
  failure_scenarios:
    - malformed structured data reaching the compose stage
---
```

```yaml
---
id: analysis:REQ-027
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.087Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
title: illustration requests are resolved from licensed web images or generated images
given: |
  - a composed section that needs an illustration no provided frame
    covers; the composer emits an illustration request (purpose in the
    lecture language, English search query, generation prompt) instead
    of a frame figure
when: the notes stage resolves illustration requests after composition
then: |
  for each request, at most one per section (analysis:ASM-022), the
  resolver searches Wikimedia Commons (analysis:EXT-012) for the
  configured number of candidates and grades them in relevance order
  through the vision check port, which returns a domain-neutral 0-100
  fit score against the request purpose; the verdict is derived from
  fixed thresholds — perfect (score >= 85), suitable (score >= 50),
  unsuitable below. The first candidate graded perfect is taken
  immediately (remaining candidates are not graded). When no candidate
  is perfect: with image generation enabled (pipeline:CON-001
  --generated-images) and the per-lecture cap not reached, one image is
  generated through the image generation port (analysis:EXT-013),
  graded the same way and taken only when graded perfect; otherwise —
  and always when generation is disabled — the suitable Commons
  candidate with the highest score (earlier search rank wins ties) is
  taken. The taken Commons image is downloaded into the work directory
  and becomes a figure block with provenance "commons", source_ref the
  HTTPS Commons file page URL and the request purpose as caption; a
  taken generated image becomes a figure block with provenance
  "generated", source_ref "generated:codex" and a caption that states
  the image is AI-generated (ru "Иллюстрация сгенерирована ИИ", en
  "AI-generated illustration"). A request with no candidate graded at
  least suitable is dropped and logged; the run continues.
negative_cases:
  - Commons search failure (network, non-200) => no candidates; with
    generation enabled the request falls through to generation,
    otherwise it is dropped
  - generation port failure, or a generated image graded below perfect
    => the best suitable Commons candidate is used; none => dropped
  - vision check port failure => the candidate counts as unsuitable
out_of_scope:
  - copyright clearance beyond citing the Commons file page
  - editing or retouching generated images
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: multi_no_shared_mutable
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    With fake search, generation and vision-check ports: the first
    perfect Commons candidate is taken and later candidates are not
    graded; without a perfect candidate and with generation enabled, a
    perfect generated image is taken, while a generated image below
    perfect falls back to the best suitable Commons candidate by score
    (earlier rank wins ties); with generation disabled the generator is
    never invoked and the best suitable candidate is taken; nothing at
    least suitable drops the request while every other block survives;
    a vision check failure is treated as unsuitable.
  test_template: unit
  boundary_classes:
    - perfect commons taken, grading stops early
    - no perfect, generation enabled => perfect generated taken
    - generated below perfect => best suitable commons by score
    - generation disabled => generator not invoked, best suitable taken
    - nothing suitable => dropped, other blocks survive
    - vision check raises => unsuitable
  failure_scenarios:
    - unverified external or generated image reaching the notes artifact
    - generated figure without the AI-generated caption
---
```

```yaml
---
id: analysis:REQ-028
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-25T19:24:19.653Z
    change_request: "trust batch: model-added verification, ledger precision, quiz v2 (user triage 2026-08-25, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
title: model-added material is verified before publication
given: |
  - composed notes whose fact and definition blocks carry an origin
    (analysis:CON-022): "lecture" when the statement is directly stated
    or clearly entailed by the lecture, "model_added" when the
    generation model introduced it
when: the notes stage assembles the final notes
then: |
  every fact block and every definition block becomes one checkable
  claim (the fact text verbatim; for a definition "term — text") and
  passes the same verification pipeline as lecturer claims
  (analysis:REQ-022 ports, batching and verdict gate). Sanctions by
  origin: a model_added fact block stays only when its verdict is
  confirmed, otherwise it is dropped; a model_added definition is
  dropped when disputed; lecture-origin blocks are never dropped — a
  disputed one is kept and followed by a factcheck_note block carrying
  the annotation and source. Every verification outcome is recorded in
  the notes artifact (verified_additions, analysis:CON-022) with the
  action taken, so the claim ledger can show model-added rows.
negative_cases:
  - verification port failure for a block's claim => the outcome is
    unverified; sanctions above apply (a model_added fact is dropped)
  - a notes artifact regenerated from checkpoints reuses the stored
    verified_additions; no re-verification on resume
out_of_scope:
  - verifying prose paragraphs and figure captions
  - rewriting lecturer wording (analysis:REQ-022 stands)
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: multi_no_shared_mutable
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    With a fake verification port: a model_added fact graded unverified
    or disputed disappears from the assembled notes while confirmed
    ones stay; a model_added disputed definition disappears; a
    lecture-origin disputed fact stays and gains a trailing
    factcheck-style warning; every processed block appears in
    verified_additions with its action; blocks other than fact and
    definition are never sent to verification.
  test_template: unit
  boundary_classes:
    - model_added fact confirmed => kept
    - model_added fact unverified => dropped
    - model_added definition disputed => dropped
    - lecture fact disputed => kept with warning
    - prose never verified
  failure_scenarios:
    - an unverified model-added fact reaching the PDF
---
```

## 7. Data contracts

```yaml
---
id: analysis:CON-020
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: segments.json payload (segmentation artifact)
surface_ref: analysis:SUR-020
schema:
  envelope: pipeline:CON-002 with stage "segmentation"
  payload_fields:
    - name: lecture_title
      type: string
      note: concise subject-matter title of the whole lecture
    - name: sections_plan
      type: array
      note: hierarchical outline; a plan entry may carry nested
        subsections of the same shape (maximum depth 2, dotted ids);
        the notes stage mirrors this outline instead of inventing its
        own structure
      items:
        - name: section_id
          type: string
        - name: title
          type: string
        - name: start_seconds
          type: number
        - name: end_seconds
          type: number
        - name: subsections
          type: array
          note: nested entries of the same shape; always empty inside a
            subsection
    - name: spans
      type: array
      items:
        - name: start_seconds
          type: number
        - name: end_seconds
          type: number
        - name: label
          type: enum
          values: [core, tangent, anecdote, admin]
        - name: section_id
          type: "string | null"
          note: null for non-core spans
        - name: reason
          type: "string | null"
          note: non-null for non-core spans (the cut log entry)
preconditions:
  - transcript artifact exists (extraction:CON-011)
postconditions:
  - spans satisfy analysis:INV-020
  - every non-core span has a non-null reason
  - plan nesting depth never exceeds 2; plan ids are unique across the
    tree
external_identifiers:
  - payload field names lecture_title, sections_plan, spans, section_id,
    title, label, reason, start_seconds, end_seconds, subsections
compatibility_rules:
  - renaming or removing a payload field => major bump on SUR-020
  - adding an optional payload field => minor bump on SUR-020
error_taxonomy:
  - "labeling port failure => stage fails, run exits 1"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    Fixture round-trips including a nested plan; a non-core span with
    null reason is rejected; an unknown label is rejected; depth-3 plan
    nesting is rejected.
  test_template: unit
  boundary_classes:
    - valid round-trip with nested plan
    - null reason on tangent => rejected
    - unknown label => rejected
    - depth-3 plan => rejected
  failure_scenarios:
    - cut without a recorded reason
---
```

```yaml
---
id: analysis:CON-021
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: claims.json payload (factcheck artifact)
surface_ref: analysis:SUR-020
schema:
  envelope: pipeline:CON-002 with stage "factcheck"
  payload_fields:
    - name: claims
      type: array
      items:
        - name: claim_id
          type: string
          note: '"c_" plus the zero-padded position in this artifact;
            stable across retries of the same run'
        - name: claim_text
          type: string
          note: lecturer's statement verbatim; never rewritten
        - name: span_start_seconds
          type: number
        - name: span_end_seconds
          type: number
        - name: verdict
          type: enum
          values: [confirmed, disputed, mixed, unverified]
          note: mixed = correct or incorrect depending on scope,
            terminology or pedagogical simplification
        - name: sources
          type: array
          note: HTTPS URLs or DOIs, deduplicated; per analysis:INV-021
            non-empty for confirmed/disputed/mixed
        - name: annotation
          type: "string | null"
          note: one-sentence rationale; non-null for disputed and mixed
            claims, null otherwise
        - name: corrected_text
          type: "string | null"
          note: precise wording for the ledger of a disputed claim;
            null otherwise
preconditions:
  - segments artifact exists (analysis:CON-020)
postconditions:
  - claims satisfy analysis:INV-021
external_identifiers:
  - payload field names claims, claim_id, claim_text,
    span_start_seconds, span_end_seconds, verdict, sources, annotation,
    corrected_text
compatibility_rules:
  - renaming or removing a payload field => major bump on SUR-020
  - adding an optional payload field => minor bump on SUR-020
error_taxonomy:
  - "verification port failure for one claim => that claim is stored as
    unverified; the stage completes"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    Fixture round-trips; a confirmed claim with empty sources is
    rejected; a disputed or mixed claim with null annotation is
    rejected; claim ids follow the positional scheme.
  test_template: unit
  boundary_classes:
    - valid round-trip incl. mixed and corrected_text
    - confirmed with empty sources => rejected
    - disputed or mixed without annotation => rejected
  failure_scenarios:
    - verdict without evidence stored as confirmed
---
```

```yaml
---
id: analysis:CON-022
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: notes.json payload (notes artifact)
surface_ref: analysis:SUR-020
schema:
  envelope: pipeline:CON-002 with stage "notes"
  payload_fields:
    - name: title
      type: string
    - name: language
      type: string
    - name: verified_additions
      type: array
      note: one record per verified fact/definition block
        (analysis:REQ-028); items {text, origin, kind, verdict,
        sources, annotation, action} with action in
        [kept, dropped, kept_with_warning]
    - name: sections
      type: array
      note: top-level sections; each section may carry nested
        subsections of the same shape (subsections themselves MUST NOT
        nest further — maximum depth is 2)
      items:
        - name: section_id
          type: string
          note: unique across the whole tree; subsection ids use the
            parent id plus a dotted suffix ("s3.1")
        - name: title
          type: string
        - name: source_spans
          type: array
          note: "[start_seconds, end_seconds] pairs into the lecture"
        - name: subsections
          type: array
          note: nested sections of the same shape; empty for leaf
            sections and always empty inside a subsection
        - name: blocks
          type: array
          note: ordered content blocks
          items:
            - name: kind
              type: enum
              values: [prose, definition, fact, figure, factcheck_note,
                table, diagram, chart]
            - name: text
              type: "string | null"
              note: for prose, definition, fact and factcheck_note; inline
                term emphasis is marked as **term** and rendered
                visually distinct (output:CON-030)
            - name: term
              type: "string | null"
              note: the defined term; non-null exactly for definition
                blocks
            - name: image_path
              type: "string | null"
              note: for figure — path under the work directory
            - name: caption
              type: "string | null"
              note: for figure, table, diagram and chart
            - name: source_ref
              type: "string | null"
              note: "required for figure per analysis:REQ-024: 'video
                HH:MM:SS' for provenance video_frame, the HTTPS Commons
                file page URL for provenance commons, 'generated:codex'
                for provenance generated"
            - name: claim_ref
              type: "integer | null"
              note: index into claims for factcheck_note
            - name: origin
              type: "enum | null"
              values: [lecture, model_added]
              note: non-null exactly for fact and definition blocks
                (analysis:REQ-028)
            - name: provenance
              type: "enum | null"
              values: [video_frame, commons, generated]
              note: non-null exactly for figure blocks
            - name: table
              type: "object | null"
              note: "non-null exactly for table blocks: {columns:
                [string], rows: [[string]]}"
            - name: diagram
              type: "object | null"
              note: "non-null exactly for diagram blocks: {kind: enum
                [hierarchy, flow], nodes: [{id: string, label: string}],
                edges: [{source: string, target: string, label: string |
                null}]}"
            - name: chart
              type: "object | null"
              note: "non-null exactly for chart blocks: {kind: enum [bar,
                line], categories: [string], series: [{name: string,
                values: [number]}], x_title: string | null, y_title:
                string | null}"
preconditions:
  - segments, claims and frames artifacts exist
postconditions:
  - every figure block has non-null image_path, source_ref and
    provenance
  - every factcheck_note block references an existing claim index
  - every definition block has non-null term and text
  - every table block has at least one column and one row and every
    row has exactly as many cells as there are columns
  - every diagram block has at least two nodes with unique ids and
    every edge references declared node ids
  - every chart block has at least one category and one series and
    every series has exactly as many values as there are categories
  - every fact and definition block has non-null origin
  - term, caption, table cells and diagram/chart labels carry no
    literal ** emphasis markers
  - section nesting depth never exceeds 2; section_id values are unique
    across the whole tree
external_identifiers:
  - payload field names title, language, sections, section_id,
    source_spans, subsections, blocks, kind, text, term, image_path,
    caption, source_ref, claim_ref, origin, provenance, table, diagram,
    chart, verified_additions
  - the inline emphasis marker "**"
compatibility_rules:
  - renaming or removing a payload field => major bump on SUR-020
  - adding an optional payload field => minor bump on SUR-020
error_taxonomy:
  - "notes port failure => stage fails, run exits 1"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    Fixture round-trips; a figure block missing source_ref or image_path
    is rejected; a factcheck_note with an out-of-range claim_ref is
    rejected; a definition block without term is rejected; a term on a
    non-definition block is rejected; structured blocks round-trip and
    violations of their data postconditions are rejected.
  test_template: unit
  boundary_classes:
    - valid round-trip with definition and fact blocks
    - valid round-trip with table, diagram and chart blocks
    - ragged table, dangling diagram edge, series length mismatch =>
      rejected
    - valid round-trip with nested subsections
    - depth-3 nesting => rejected
    - duplicate section_id across the tree => rejected
    - figure without source_ref => rejected
    - dangling claim_ref => rejected
    - definition without term => rejected
  failure_scenarios:
    - notes artifact accepted with a dangling claim reference
---
```

```yaml
---
id: analysis:CON-023
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: quiz.json payload (quiz artifact)
surface_ref: analysis:SUR-020
schema:
  envelope: pipeline:CON-002 with stage "quiz"
  payload_fields:
    - name: questions
      type: array
      items:
        - name: question_id
          type: string
        - name: type
          type: enum
          values: [single_choice, multi_select, open]
          note: reading a legacy "mcq" value migrates it by
            correct-option count (analysis:DLT-033)
        - name: prompt
          type: string
        - name: options
          type: "array | null"
          note: exactly 4 strings for single_choice/multi_select; null
            for open
        - name: correct_options
          type: "array | null"
          note: unique 0-based indices — exactly one for single_choice,
            at least two for multi_select; null for open
        - name: model_answer
          type: "string | null"
          note: non-null for open (reference answer); null otherwise
        - name: rubric
          type: "object | null"
          note: "non-null exactly for open questions: {max_points:
            integer, concepts: [{description: string, points:
            integer}]}; concept points sum to max_points"
        - name: section_id
          type: string
          note: resolves into analysis:CON-022 sections
preconditions:
  - notes artifact exists (analysis:CON-022)
postconditions:
  - question count and shapes per analysis:REQ-023
external_identifiers:
  - payload field names questions, question_id, type, prompt, options,
    correct_options, model_answer, rubric, section_id
compatibility_rules:
  - renaming or removing a payload field => major bump on SUR-020
  - adding an optional payload field => minor bump on SUR-020
error_taxonomy:
  - "quiz port failure => stage fails, run exits 1"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
  - pipeline:POL-002
test_obligation:
  predicate: |
    Fixture round-trips; a single_choice with two correct options is
    rejected; a multi_select with one correct option is rejected; an
    open question without a rubric or with concept points not summing
    to max_points is rejected; a legacy "mcq" payload migrates by
    correct-option count.
  test_template: unit
  boundary_classes:
    - valid round-trip of all three types
    - single_choice with two correct => rejected
    - multi_select with one correct => rejected
    - open without rubric or with bad point sum => rejected
    - legacy mcq migrated
  failure_scenarios:
    - malformed question rendered into the PDF
---
```

## 8. Invariants

```yaml
---
id: analysis:INV-020
type: Invariant
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: labeled spans cover the transcript timeline exactly
always: |
  In every stored segments.json payload, the spans, ordered by
  start_seconds, form a partition of the transcript timeline
  [first_segment.start_seconds, last_segment.end_seconds): consecutive
  spans meet without gap or overlap (tolerance 0.5 seconds), the first
  span starts at the timeline start and the last span ends at the
  timeline end within the same tolerance.
scope: konspekt/analysis-artifacts
evidence: public_api
stability: contractual
data_scope: all_data
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: none
negative_cases:
  - a gap of more than 0.5 seconds between consecutive spans is invalid
  - overlapping spans are invalid
out_of_scope:
  - silence trimming before the first utterance
test_obligation:
  predicate: |
    The coverage validator accepts a gapless fixture, rejects a fixture
    with a 1-second gap naming the gap position, and rejects overlapping
    spans.
  test_template: unit
  boundary_classes:
    - exact cover
    - gap at 0.5s tolerance boundary
    - overlap
  failure_scenarios:
    - lecture minutes silently lost between spans
---
```

```yaml
---
id: analysis:INV-021
type: Invariant
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
title: confirmed and disputed verdicts cite evidence from the search
always: |
  In every stored claims.json payload, every claim with verdict
  "confirmed", "disputed" or "mixed" has a non-empty sources array and
  every entry is the URL of evidence that the evidence search
  (analysis:EXT-014) returned for that claim during the run; a claim
  without such a source carries verdict "unverified".
scope: konspekt/analysis-artifacts
evidence: public_api
stability: contractual
data_scope: all_data
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: none
negative_cases:
  - a URL or DOI produced by the model that is not in the claim's
    evidence MUST downgrade the verdict to unverified
out_of_scope:
  - re-validating sources after the run (link rot)
  - whether a source page answers a bot request at fact-check time
test_obligation:
  predicate: |
    The verdict gate keeps a confirmed, disputed or mixed verdict whose
    sources all belong to the claim's evidence URLs, and downgrades it
    to unverified when a source lies outside that set or the sources
    are empty.
  test_template: unit
  boundary_classes:
    - evidence source kept
    - source outside the evidence downgraded
    - empty sources downgraded
  failure_scenarios:
    - fabricated citation surviving into the PDF
---
```

```yaml
---
id: analysis:INV-022
type: Invariant
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.147Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
title: web and generated figures pass a vision check before storage
always: |
  In every stored notes.json payload, every figure block with
  provenance "commons" or "generated" was confirmed by the vision check
  port against the request purpose before the notes artifact was
  written; figure blocks with provenance "video_frame" reference a
  frame of the frames artifact whose timestamp lies inside the owning
  section's source spans.
scope: konspekt/analysis-artifacts
evidence: test_probe
stability: internal
data_scope: all_data
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: none
negative_cases:
  - a Commons candidate the vision check rejects MUST NOT become a
    figure even when it downloads fine
out_of_scope:
  - re-checking images after the run
test_obligation:
  predicate: |
    The illustration resolver with a fake vision check that rejects
    every candidate stores no commons/generated figures; with a check
    that confirms, the stored figure carries the confirmed candidate.
  test_template: unit
  boundary_classes:
    - rejecting check => no figure
    - confirming check => figure stored
  failure_scenarios:
    - unchecked image stored as a figure
---
```

## 9. External dependencies

```yaml
---
id: analysis:EXT-010
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
provider: Anthropic Claude API
provider_surface: "anthropic-api@2023-06-01 (POST /v1/messages, model claude-opus-5)"
authority_url_or_doc: "https://platform.claude.com/docs/en/api"
consumer_contract:
  request:
    - messages.create / messages.parse with model from stage
      configuration (default claude-opus-5)
    - structured outputs (output_config.format json_schema) for
      segmentation, notes structure, quiz
    - claim verification and claim query translation send no tools;
      the verification request carries the claim evidence
      (analysis:REQ-022)
    - image content blocks (frames) for figure selection in notes
  response_expectations:
    - JSON conforming to the requested schema in parsed output
    - usage fields for budget accounting (pipeline:POL-002)
    - stop_reason "refusal" handled as stage failure with typed error
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-19
auth_scope:
  - api key via env var ANTHROPIC_API_KEY
rate_limits:
  - provider tier limits; claim verification and per-section notes
    composition run up to 4 concurrent requests each, every other stage
    stays within one concurrent request
retry/idempotency:
  - SDK default retries (429/5xx); requests carry no server-side state
error_taxonomy:
  - 401 => run exits 2
  - refusal stop_reason => stage fails, run exits 1
  - schema-mismatch in parsed output => one re-request, then stage fails
sandbox_or_fixture:
  - all unit tests use fake ports; no live Anthropic calls in CI
test_obligation:
  predicate: |
    Every LLM-facing use case (segmentation plan, span labeling, claim
    extraction, claim query translation, claim verification, notes
    composition, figure selection, quiz generation) is exercised against
    fake ports in unit tests; the
    budget accountant receives the usage numbers the fake reports.
  test_template: contract
  boundary_classes:
    - each use case over its fake port
  failure_scenarios:
    - use case bypassing the budget accountant
---
```

```yaml
---
id: analysis:EXT-011
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T20:35:09.974Z
    change_request: switch LLM stages to subscription claude CLI per user instruction 2026-08-19
    scope: first-time-approval
partition_id: analysis
provider: Claude Code CLI (subscription-authenticated local binary)
provider_surface: "claude-code-cli@>=2.1 (claude -p --output-format json)"
authority_url_or_doc: "https://code.claude.com/docs/en/cli-reference"
consumer_contract:
  invocations:
    - cmd: "claude -p --output-format json --model <model> [--allowedTools <tools>]"
      stdin: the prompt text
      expects:
        - exit 0; stdout is one JSON object with fields result (string),
          is_error (bool), stop_reason, total_cost_usd (number)
        - is_error true => stage failure
  tool_grants:
    - claim verification passes no tools; the claim evidence is part of
      the prompt (analysis:REQ-022)
    - claim query translation for a non-English lecture passes no tools
    - notes figure selection passes --allowedTools "Read" and references
      frame image paths in the prompt
  authentication: managed by Claude Code itself (subscription login);
    no API key enters the pipeline environment
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-19
auth_scope:
  not_applicable: cli_manages_own_login
  reason: the binary holds the user's subscription session; the
    pipeline passes no credentials
rate_limits:
  - subscription plan limits enforced by the provider; claim
    verification and per-section notes composition run up to 4
    concurrent invocations each, every other stage stays
    single-threaded
retry/idempotency:
  - schema-mismatch in the result JSON => one re-request, then stage
    fails (same rule as analysis:EXT-010)
error_taxonomy:
  - binary absent on PATH => run exits 2 before any stage
  - is_error true or non-zero exit => stage fails, run exits 1
sandbox_or_fixture:
  - unit tests inject a fake runner or a stub executable; no live
    claude invocations in CI
test_obligation:
  predicate: |
    Every CLI-provider adapter (segmentation, factcheck, notes, quiz)
    is exercised against a fake runner: prompt passed via stdin, model
    forwarded, budget charged with total_cost_usd from the parsed
    output, is_error mapped to a typed stage error, schema-mismatch
    retried exactly once.
  test_template: contract
  boundary_classes:
    - each adapter over the fake runner
    - is_error true
    - schema-mismatch retry
  failure_scenarios:
    - adapter bypassing the budget accountant
    - malformed CLI output crashing instead of typed failure
---
```

```yaml
---
id: analysis:EXT-012
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.208Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
provider: Wikimedia Commons (MediaWiki Action API)
provider_surface: "https://commons.wikimedia.org/w/api.php (action=query, generator=search, prop=imageinfo)"
authority_url_or_doc: "https://www.mediawiki.org/wiki/API:Search"
consumer_contract:
  request:
    - GET api.php?action=query&format=json&generator=search&gsrsearch=<query>&gsrnamespace=6&gsrlimit=<n>&prop=imageinfo&iiprop=url|mime|size|extmetadata&iiurlwidth=1200
    - User-Agent header identifying konspekt with a contact URL
  response_expectations:
    - pages[*].imageinfo[0] carries url, thumburl, mime, width, height,
      extmetadata (LicenseShortName, Artist); pages[*].title is the
      "File:..." name, the file page URL is
      https://commons.wikimedia.org/wiki/<title>
    - only image/jpeg and image/png candidates are used; SVG and other
      mimes are skipped
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-22
auth_scope:
  not_applicable: anonymous_read_api
  reason: search and image info need no authentication
rate_limits:
  - "anonymous etiquette: sequential requests per worker, at most 3
    workers, one search per illustration request"
retry/idempotency:
  - network error or non-200 => no candidates (falls through to
    generation, analysis:REQ-027); no retry
error_taxonomy:
  - non-200 or malformed JSON => empty candidate list
sandbox_or_fixture:
  - unit tests use a fake httpx transport with a recorded response
    fixture; no live requests in CI
test_obligation:
  predicate: |
    The Commons adapter maps a recorded API response to candidates
    (file page URL, image URL, mime, license) skipping non-raster
    mimes, and returns an empty list on non-200 or malformed JSON.
  test_template: contract
  boundary_classes:
    - recorded response mapped
    - svg candidate skipped
    - non-200 => empty
    - malformed JSON => empty
  failure_scenarios:
    - adapter raising into the resolver on provider failure
---
```

```yaml
---
id: analysis:EXT-013
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.269Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
provider: OpenAI Codex CLI (subscription-authenticated local binary) with its image_gen tool
provider_surface: "codex-cli@>=0.146 (codex exec --skip-git-repo-check -s workspace-write -C <dir>)"
authority_url_or_doc: "https://github.com/openai/codex"
consumer_contract:
  invocations:
    - cmd: "codex exec --skip-git-repo-check -s workspace-write -C <dir> <prompt>"
      stdin: closed
      expects:
        - exit 0 and a PNG or JPEG file written under <dir> with the
          requested file name; the prompt asks for one educational
          illustration (textbook style, white background, labels in
          the lecture language) and names the target file
        - missing file or non-zero exit => generation failed
  authentication: managed by Codex itself (subscription login); no API
    key enters the pipeline environment
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-22
auth_scope:
  not_applicable: cli_manages_own_login
  reason: the binary holds the user's subscription session
rate_limits:
  - at most 3 concurrent generations; per-lecture cap per
    analysis:ASM-022; ~2 minutes per image observed
retry/idempotency:
  - no retry on failure; the request is dropped (analysis:REQ-027)
error_taxonomy:
  - binary absent on PATH => generation disabled for the run, logged at
    start; requests fall to "dropped"
  - non-zero exit, timeout or missing output file => generation failed
sandbox_or_fixture:
  - unit tests inject a fake generation port or a stub executable; no
    live invocations in CI
test_obligation:
  predicate: |
    The Codex adapter over a stub executable returns the produced file
    path when the file exists after exit 0 and None on non-zero exit or
    a missing file; the prompt passed to the executable names the
    target file.
  test_template: contract
  boundary_classes:
    - file produced
    - non-zero exit => None
    - exit 0 without file => None
  failure_scenarios:
    - adapter raising into the resolver on provider failure
---
```

```yaml
---
id: analysis:EXT-014
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:14:57.566Z
    change_request: Exa evidence-first fact-check (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: analysis
provider: Exa Search API
provider_surface: "https://api.exa.ai/search (POST, type auto, contents.highlights)"
authority_url_or_doc: "https://exa.ai/docs/reference/search"
consumer_contract:
  request:
    - POST https://api.exa.ai/search with header x-api-key from the env
      var EXA_API_KEY and JSON body {query, type "auto", numResults 5,
      contents {highlights {query, maxCharacters 2000}}}
    - one request per claim and search language; the highlights query
      equals the request query
  response_expectations:
    - results[*] carries url and title; publishedDate is optional;
      highlights is a list of query-focused excerpts
    - excerpts are model input only; they are never written to the
      PDF, the Markdown bundle or any artifact
    - costDollars is an estimate and is not charged to the LLM budget
      (pipeline:POL-002); a run issues at most two searches per claim
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-09-12
auth_scope:
  - api key via env var EXA_API_KEY, handled per pipeline:POL-001
rate_limits:
  - "provider: 10 search requests per second on the free plan; the
    adapter keeps the whole run at or below 8 requests per second"
retry/idempotency:
  - 429 and 503 => up to 3 attempts, waiting Retry-After when present,
    otherwise 1 s then 2 s; exhausted retries, a 30 s timeout or any
    other non-2xx status => that query yields no evidence
  - a search is read-only; repeating it has no side effect
error_taxonomy:
  - 401 or 403 => run exits 2 (invalid or revoked EXA_API_KEY)
  - 402 => stage fails, run exits 1 (Exa credits exhausted)
  - malformed JSON => the query yields no evidence; a result without
    url is skipped
sandbox_or_fixture:
  - unit tests use a fake httpx transport with recorded responses; no
    live Exa requests in CI
test_obligation:
  predicate: |
    The Exa adapter sends the documented request (x-api-key header,
    type, numResults, highlights query) and maps a recorded response to
    evidence items (url, title, published date, excerpts); it retries
    429 and 503 for at most 3 attempts honoring Retry-After, returns no
    evidence after exhausted retries or on another non-2xx status,
    raises the typed credential error on 401/403 and the typed credits
    error on 402, and never puts the key into an exception message.
  test_template: contract
  boundary_classes:
    - recorded response mapped
    - request header and body
    - 429 then 200 => evidence
    - 503 on every attempt => no evidence
    - 401 => credential error
    - 402 => credits error
    - result without url skipped
  failure_scenarios:
    - key echoed into an exception message
    - retries exceeding the provider rate limit
---
```

## 10. Generated artifacts

None.

## 11. Localization

None as separate records: notes and quiz text are produced in the
lecture language recorded by extraction:REQ-010, which the notes and
quiz ports receive as an explicit parameter; artifact field names are
English identifiers covered by analysis:SUR-020.

## 12. Policies

None owned by this partition. `default_policy_set` applies
`pipeline:POL-001` and `pipeline:POL-002` to every boundary contract
above.

## 13. Constraints

None.

## 14. Migrations

None.

## 15. Deltas

```yaml
---
id: analysis:DLT-024
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T08:05:45.811Z
    change_request: sectioned notes composition with plan-owned outline (user, 2026-08-20)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-020
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  The hierarchical outline moves from the notes stage into the
  segmentation plan (user decision 2026-08-20): sections_plan carries
  nested subsections (depth 2) plus the lecture_title, and the notes
  stage mirrors this outline. Motivation: a single whole-lecture notes
  request hits the output-token ceiling on long lectures, dilutes
  attention across dozens of sections, and loses the entire stage on
  one defect; the outline pass stays global (whole-lecture context) so
  the structure remains coherent.
tests_old_behavior:
  - not_applicable: flat_plan_payloads_replaced_before_release
tests_new_behavior:
  - tests/features/segmentation (nested plan round-trip, depth cap)
---
```

```yaml
---
id: analysis:DLT-026
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T13:21:02.876Z
    change_request: duplication across parent/subsections found in reference lecture review (user, 2026-08-20)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-022
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  De-duplication rules for sectioned composition, after the reference
  lecture showed parent-intro text massively overlapping its own
  subsections and fact-check annotations duplicated between parent and
  child: (1) a parent's intro request receives only the core text of
  its range MINUS subsection ranges plus subsection titles; (2) every
  claim and frame is assigned to exactly one composition target — the
  most specific entry containing its midpoint; (3) after assembly,
  definition blocks repeating an already-defined term (normalized) are
  dropped, first occurrence in outline order wins, drops are logged.
tests_old_behavior:
  - not_applicable: duplication_defect_replaced_before_release
tests_new_behavior:
  - tests/features/notes (exclusive inputs, intro text exclusion,
    definition dedupe)
---
```

```yaml
---
id: analysis:DLT-027
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.391Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-022
kind: extend
compatibility_action: ignore
baseline_version: 3fd094a
summary: |
  Structured material blocks (analysis:REQ-026) and figure provenance
  (analysis:REQ-027): block kinds gain table, diagram and chart with
  the typed nested fields table {columns, rows}, diagram {kind, nodes,
  edges}, chart {kind, categories, series, x_title, y_title}; figure
  blocks gain provenance in {video_frame, commons, generated} and
  source_ref admits "generated:codex". All new fields are optional for
  existing consumers. Minor bump of SUR-020 to 0.3.0.
tests_old_behavior:
  - tests/features/notes (payloads without the new fields still parse)
tests_new_behavior:
  - tests/features/notes (structured block round-trip and rejections,
    provenance round-trip)
---
```

```yaml
---
id: analysis:DLT-028
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.453Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:REQ-024
kind: extend
compatibility_action: ignore
baseline_version: 3fd094a
summary: |
  Figure sources extend from video frames and arbitrary HTTPS URLs to
  three attributed kinds: video frames ("video HH:MM:SS"), Wikimedia
  Commons files (HTTPS file page URL) and generated images
  ("generated:codex"), each carrying provenance. Web and generated
  figures enter the notes only through the illustration resolver with a
  vision check (analysis:REQ-027, analysis:INV-022).
tests_old_behavior:
  - tests/features/notes (frame figure attribution unchanged)
tests_new_behavior:
  - tests/features/notes (commons and generated attribution, resolver)
---
```

```yaml
---
id: analysis:DLT-029
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-24T18:29:57.855Z
    change_request: source-first illustration selection, generation behind a flag (user decision 2026-08-24, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:REQ-027
kind: replace
compatibility_action: ignore
baseline_version: 33e5d88
summary: |
  Tiered, source-first illustration resolution after the third
  reference lecture showed generation outcompeting verified images
  (the exact-match check favoured images made to the request's own
  spec). The vision check becomes a domain-neutral grader returning
  perfect | suitable | unsuitable plus a 0-100 fit score. Commons
  candidates (count configurable, --commons-candidates) are graded in
  relevance order with an early stop on the first perfect one. Without
  a perfect candidate: when generation is enabled (--generated-images,
  default OFF) one image is generated and accepted only when graded
  perfect, otherwise the best suitable Commons candidate (highest
  score, earlier rank wins ties) is used; with generation disabled the
  best suitable Commons candidate is used directly. No candidate at
  least suitable => the request is dropped and logged. The grader
  prompt is subject-agnostic (no anatomy or other domain wording).
tests_old_behavior:
  - not_applicable: resolution_policy_replaced_before_release
tests_new_behavior:
  - tests/features/notes (tiered resolver, early stop, ranking,
    generation gating), tests/pipeline (flag wiring)
---
```

```yaml
---
id: analysis:DLT-030
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-24T19:14:37.190Z
    change_request: score-derived verdict thresholds 85/50 (user decision 2026-08-24, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:REQ-027
kind: extend
compatibility_action: ignore
baseline_version: 33e5d88
summary: |
  The vision check grades a candidate with a single 0-100 fit score;
  the verdict tiers of analysis:DLT-029 are derived from fixed
  thresholds instead of being asked from the model: perfect = score >=
  85, suitable = score >= 50, unsuitable below 50. Resolution logic
  (early stop on perfect, best suitable by score, generation gating)
  is unchanged.
tests_old_behavior:
  - not_applicable: refines_dlt_029_before_release
tests_new_behavior:
  - tests/features/notes (threshold boundaries, score-only adapter
    contract)
---
```

```yaml
---
id: analysis:DLT-031
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-25T19:24:19.711Z
    change_request: "trust batch: model-added verification, ledger precision, quiz v2 (user triage 2026-08-25, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-022
kind: extend
compatibility_action: ignore
baseline_version: 620e7bc
summary: |
  Model-added-content audit (analysis:REQ-028) and emphasis hygiene:
  fact and definition blocks gain the mandatory field origin
  (lecture | model_added); the payload gains verified_additions — one
  record per verified fact/definition {text, origin, kind, verdict,
  sources, annotation, action kept|dropped|kept_with_warning}; the
  fields term, caption, table cells, diagram and chart labels carry no
  literal ** emphasis markers (markers are stripped during
  normalization — emphasis lives only in prose-capable text fields).
tests_old_behavior:
  - tests/features/notes (payloads without the new fields still parse)
tests_new_behavior:
  - tests/features/notes (origin round-trip, verified_additions,
    emphasis stripped from non-prose fields)
---
```

```yaml
---
id: analysis:DLT-032
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-25T19:24:19.773Z
    change_request: "trust batch: model-added verification, ledger precision, quiz v2 (user triage 2026-08-25, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-021
kind: extend
compatibility_action: ignore
baseline_version: 620e7bc
summary: |
  Claim ledger precision: claims gain claim_id ("c_" plus zero-padded
  position, stable within one artifact), the verdict enum gains
  "mixed" (correct or incorrect depending on scope, terminology or
  pedagogical simplification; requires a resolvable source and a
  non-null annotation, same gate as disputed), and disputed claims may
  carry corrected_text — the precise wording used by the ledger, while
  the lecturer's claim_text is never rewritten.
tests_old_behavior:
  - tests/features/factcheck (payloads without the new fields parse)
tests_new_behavior:
  - tests/features/factcheck (claim_id assignment, mixed gate,
    corrected_text round-trip)
---
```

```yaml
---
id: analysis:DLT-033
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-25T19:24:19.838Z
    change_request: "trust batch: model-added verification, ledger precision, quiz v2 (user triage 2026-08-25, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-023
kind: replace
compatibility_action: migrate
baseline_version: 620e7bc
summary: |
  Quiz schema v2: the type enum becomes single_choice | multi_select |
  open (a single_choice question has exactly one correct option, a
  multi_select at least two — the former "mcq" split by its
  correct_options count); every open question gains a mandatory
  point-based rubric {max_points, concepts: [{description, points}]}
  whose points sum to max_points, alongside the reference
  model_answer. Breaking for CON-023 consumers: reading an old "mcq"
  artifact maps it onto the new types by correct-option count.
tests_old_behavior:
  - tests/features/quiz (an "mcq" payload is migrated on parse)
tests_new_behavior:
  - tests/features/quiz (type split validation, rubric totals)
---
```

```yaml
---
id: analysis:DLT-034
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:14:57.624Z
    change_request: Exa evidence-first fact-check (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:REQ-022
kind: replace
compatibility_action: ignore
baseline_version: 734063e
summary: |
  Evidence-first verification. The model no longer searches the web on
  its own: for every claim the evidence search (analysis:EXT-014)
  returns up to 5 sources with query-focused excerpts, searched in the
  lecture language and, for a non-English lecture, also in English;
  the English queries come from one translation request per batch.
  One verification request per batch of up to 5 claims grades each
  claim only against its own numbered evidence and cites evidence by
  number; the stored sources are the URLs of the cited evidence. A
  failed or empty search leaves the claim unverified. Stored
  claims.json artifacts stay valid and are not re-verified.
tests_old_behavior:
  - tests/features/factcheck (stored claims payloads parse unchanged)
tests_new_behavior:
  - tests/features/factcheck (evidence-first verification over fake
    search and verification ports, English queries for non-English
    lectures, citation by evidence number)
---
```

```yaml
---
id: analysis:DLT-035
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:14:57.684Z
    change_request: Exa evidence-first fact-check (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:INV-021
kind: replace
compatibility_action: ignore
baseline_version: 734063e
summary: |
  The source predicate changes from "the first source answered an HTTP
  request with status < 400 at fact-check time" to "every stored source
  is the URL of evidence that the search (analysis:EXT-014) returned for
  that claim in this run, and there is at least one". The HEAD/GET
  probe is removed: it rejected real pages that refuse bots (HTTP 403
  from Wikipedia and Britannica) and downgraded 65-70% of the verdicts
  in the recorded runs. Predicate change on a contractual invariant =>
  analysis:SUR-020 2.0.0.
tests_old_behavior:
  - tests/features/factcheck (stored claims payloads parse unchanged)
tests_new_behavior:
  - tests/features/factcheck/test_verdict_gate.py (evidence source kept,
    source outside the evidence and empty sources downgraded)
---
```

```yaml
---
id: analysis:DLT-036
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:14:57.745Z
    change_request: Exa evidence-first fact-check (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:EXT-011
kind: replace
compatibility_action: ignore
baseline_version: 734063e
summary: |
  Claim verification over the CLI no longer grants the WebSearch tool:
  it runs without tools and receives the claim evidence in the prompt
  (analysis:DLT-034). A new invocation, also without tools, translates
  a batch of claims into English search queries for a non-English
  lecture. The Read grant for figure selection and vision checks is
  unchanged.
tests_old_behavior:
  - tests/features/factcheck (claim extraction over the fake runner
    unchanged)
tests_new_behavior:
  - tests/features/factcheck/test_claude_cli_factcheck.py (no tool
    grant, evidence in the prompt, cited numbers mapped to URLs,
    translation over the fake runner)
---
```

```yaml
---
id: analysis:DLT-037
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:14:57.807Z
    change_request: Exa evidence-first fact-check (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:EXT-010
kind: replace
compatibility_action: ignore
baseline_version: 734063e
summary: |
  Claim verification over the API no longer sends the
  web_search_20260209 server tool; the request carries the claim
  evidence and the model grades it (analysis:DLT-034). Query
  translation for a non-English lecture is one more request per batch,
  also without tools.
tests_old_behavior:
  - tests/features/factcheck (claim extraction over the fake client
    unchanged)
tests_new_behavior:
  - tests/features/factcheck/test_claude_factcheck.py (no tools in the
    request, evidence in the request, cited numbers mapped to URLs,
    translation over the fake client)
---
```

```yaml
---
id: analysis:DLT-025
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T08:05:45.870Z
    change_request: sectioned notes composition with plan-owned outline (user, 2026-08-20)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-022
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  Notes composition decomposes into independent-context per-section
  requests (up to 4 concurrent): each request receives the global
  outline (coherence, no-repeat and first-introduction rules), its own
  core text, claim subset with GLOBAL claim indices, and frames of its
  time range; a parent with subsections receives a brief-intro request
  only. The notes.json artifact shape (CON-022) is unchanged: the
  section tree mirrors the segmentation plan and claim_ref stays a
  global index into claims.json. Failure or schema-mismatch is retried
  per section, not per lecture.
tests_old_behavior:
  - not_applicable: internal_decomposition_artifact_shape_unchanged
tests_new_behavior:
  - tests/features/notes (per-section assembly, global claim_ref,
    parallel order preserved, per-section retry isolation)
---
```

```yaml
---
id: analysis:DLT-023
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T07:40:02.329Z
    change_request: full-lecture regen lost to strict media validation (2026-08-20)
    scope: first-time-approval
partition_id: analysis
target_id: analysis:REQ-024
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  Misplaced frame figures (timestamp outside the section source spans)
  are dropped with a run-log record instead of failing the notes stage:
  a live full-lecture run lost an eight-minute composition to two
  misplaced illustrations. Attribution and validation of surviving
  figures are unchanged.
tests_old_behavior:
  - not_applicable: stricter_failure_mode_replaced_before_release
tests_new_behavior:
  - tests/features/notes (out-of-span figure dropped, notes survive)
---
```

```yaml
---
id: analysis:DLT-022
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T21:58:09.630Z
    change_request: "acceptance feedback round 3: hierarchical sections (user, 2026-08-19)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-022
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  Hierarchical notes structure per user acceptance feedback round 3
  (2026-08-19): sections may carry nested subsections (maximum depth 2,
  dotted subsection ids); quiz coverage (analysis:REQ-023) counts
  top-level sections, a subsection question credits its parent. Long
  lectures require a real outline; the small reference clip stays flat.
tests_old_behavior:
  - tests/features/notes (flat payloads keep round-tripping unchanged)
tests_new_behavior:
  - tests/features/notes (nested round-trip, depth cap, unique ids)
  - tests/features/quiz (subsection question credits the parent)
---
```

```yaml
---
id: analysis:DLT-020
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T21:20:19.952Z
    change_request: "acceptance feedback round 1: rich markup, multi-correct quiz export, full coverage (user, 2026-08-19)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-022
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  Typed study-material blocks per user acceptance feedback (2026-08-19):
  block kinds gain "definition" (with a mandatory term field) and
  "fact"; prose and definition text may carry inline **term** emphasis
  markers rendered visually distinct in the PDF. No stored artifacts
  predate this change outside disposable work directories.
tests_old_behavior:
  - not_applicable: no_released_consumers_of_v0_1_payloads
tests_new_behavior:
  - tests/features/notes (definition/fact round-trip and rejection)
---
```

```yaml
---
id: analysis:DLT-021
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T21:20:20.012Z
    change_request: "acceptance feedback round 1: rich markup, multi-correct quiz export, full coverage (user, 2026-08-19)"
    scope: first-time-approval
partition_id: analysis
target_id: analysis:CON-023
kind: replace
compatibility_action: reject
baseline_version: a3b7f19
summary: |
  Quiz contract v0.2.0 per user acceptance feedback (2026-08-19):
  correct_option (single index) is replaced by correct_options
  (non-empty array, multiple correct answers allowed); analysis:REQ-023
  gains the full-coverage rule (every section >= 1 question, total >=
  max(10, 2 x sections)). Old payloads with correct_option are rejected
  by serde (schema_version stays 1; the field rename is the breaking
  marker; work directories are disposable).
tests_old_behavior:
  - tests/features/quiz (payload with correct_option is rejected)
tests_new_behavior:
  - tests/features/quiz (multi-correct round-trip, coverage validation)
---
```

## 16. Implementation bindings

None yet.

## 17. Open questions

```yaml
---
id: analysis:OQ-020
type: Open-Q
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
question: |
  Fact-check literature search: is the Anthropic web_search tool alone
  sufficient for MVP, or is a direct scholarly-API integration
  (OpenAlex / Crossref) required before acceptance?
options:
  - id: a
    label: web_search_only_mvp
    consequence: |
      One provider, simpler budget control via max_uses; scholarly
      coverage depends on what web search surfaces.
  - id: b
    label: add_openalex_crossref
    consequence: |
      Better DOI-grade sources for scientific lectures; adds two
      ExternalDependency records, more code and failure modes in MVP.
blocking: no
owner: cyberash
default_if_unresolved: a
---
```

## 18. Assumptions

```yaml
---
id: analysis:ASM-020
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
assumption: |
  MVP fact-checking uses the Anthropic web_search tool only (option a of
  analysis:OQ-020); source resolvability is enforced by analysis:INV-021
  regardless of where the URL came from.
source_open_q: analysis:OQ-020
blocking: no
review_by: 2026-10-01
default_if_unresolved: keep_assumption
tests:
  - tests/features/factcheck (verdict gate tests)
---
```

```yaml
---
id: analysis:ASM-021
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.315Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: analysis
assumption: |
  Default quiz size is max(10, 2 x section count) questions per lecture
  (roughly 70% mcq / 30% open), configurable; coverage per
  analysis:REQ-023 requires every section referenced at least once.
blocking: no
review_by: 2026-10-01
default_if_unresolved: keep_assumption
tests:
  - tests/features/quiz (count and shape tests)
---
```

```yaml
---
id: analysis:ASM-022
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:01.330Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: analysis
assumption: |
  Illustration resolution defaults: at most 1 illustration request per
  composed section (extra requests are dropped); 6 Commons candidates
  per request (overridable via --commons-candidates); image generation
  disabled unless --generated-images is passed, capped at 8 generated
  images per lecture when enabled; 3 concurrent resolutions; the
  vision check uses the notes model and scores 0-100 with verdict
  thresholds perfect >= 85 and suitable >= 50. Values are tuned on the
  third reference lecture.
blocking: no
review_by: 2026-10-15
default_if_unresolved: keep_assumption
tests:
  - tests/features/notes (cap boundary tests reference the configured
    values, not literals)
---
```

## 19. Out of scope

- Exhaustive verification of every sentence of the lecture.
- Copyright clearance for external images (source is cited; usage
  rights remain the user's responsibility).
- Adaptive quizzes, spaced repetition, learner progress tracking.
