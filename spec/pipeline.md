# `konspekt` — Partition `pipeline`

> Composition root: CLI surface, stage-artifact envelope, resumability,
> secrets and budget policies. Written per
> `~/.claude/rules/spec-driven-development.md`.

---

## 1. Context

`konspekt` turns a recorded lecture video (1-2 hours, Russian or English)
into a fact-checked study-notes PDF with a self-check quiz. The system is
a local CLI pipeline of eight stages (ingest, transcription, visual,
segmentation, factcheck, notes, quiz, compose). Each stage reads and
writes JSON artifacts on disk; expensive API stages are skipped on re-run
when their inputs are unchanged. This partition owns the CLI, the
artifact envelope shared by every stage, resumability, and the
cross-cutting secret and budget policies.

## 2. Glossary

- **Stage** — one of the eight pipeline steps, enumerated in
  `pipeline:CON-002`.
- **Artifact** — a JSON file written by a stage into the work directory,
  wrapped in the envelope defined by `pipeline:CON-002`.
- **Work directory** — `<out>/<lecture-slug>/work/`, where `<out>` is the
  output directory from `pipeline:CON-001` and `<lecture-slug>` is the
  video file name without extension, lowercased, Cyrillic letters
  transliterated to Latin, remaining characters outside `[a-z0-9-]`
  replaced by `-`, consecutive `-` collapsed, leading and trailing `-`
  removed; an empty result falls back to `lecture`.
- **Input fingerprint** — sha256 hex over the concatenation of: the
  sha256 of every input artifact of the stage (in stage order) and the
  canonical JSON of the stage configuration.
- **Stage configuration** — the subset of run configuration a stage
  declares as affecting its output (model id, language, thresholds).
- **Budget** — the maximum total LLM spend in USD for one `konspekt build`
  run, from configuration key `max_llm_usd`.

## 3. Partition

```yaml
---
id: pipeline
type: Partition
partition_id: pipeline
owner_team: cyberash
gate_scope:
  - pipeline
dependencies_on_other_partitions: []
default_policy_set:
  - pipeline:POL-001
  - pipeline:POL-002
id_namespace: pipeline
unmodeled_budget:
  current: 0
  baseline_at: "2026-08-19"
  baseline_value: 0
  trend: monotonic_non_increasing
---
```

## 4. Brownfield baseline

```yaml
---
id: pipeline:BL-001
type: BrownfieldBaseline
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
discovery_scope:
  - src
  - tests
  - pyproject.toml
coverage_evidence:
  - kind: git_tree_hash_v1
    reference: 9f61fd77f21a0bf4aea912131eda17f2da166484
    note: |
      Greenfield project: the baseline covers the initial package
      skeleton only. spec/ and .sdd/config.json stay outside the scope
      because BL-001 stores the token inside spec/pipeline.md; including
      them would make the token self-referential.
freshness_token: 18fad9d042c967af338591f6b313e54d2af812f5681727bfbc0690c5e3452a11
baseline_commit_sha: 9f61fd77f21a0bf4aea912131eda17f2da166484
mechanism: git_tree_hash_v1
notes: |
  Greenfield baseline: no pre-existing behavior is preserved.
  Refreshed after M1+M2: every scope change implements approved IDs
  of this spec revision; no unmodeled behavior was introduced.
---
```

## 5. Surfaces

```yaml
---
id: pipeline:SUR-001
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
name: konspekt/cli
version: "0.4.0"
boundary_type: cli
members:
  - pipeline:CON-001
consumer_compat_policy: semver_per_surface
notes: |
  v0.4.0 — breaking (pre-1.0): EXA_API_KEY is required for every build
  (pipeline:DLT-005).
  v0.3.0 — additive: flags --commons-candidates and --generated-images
  (pipeline:DLT-004). Existing invocations are unchanged.
  v0.2.0 — additive: flags --llm-provider and --transcriber with
  defaults (pipeline:DLT-001). Existing invocations are unchanged.
  v0.1.0 — original build command.
---
```

```yaml
---
id: pipeline:SUR-003
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T09:05:44.958Z
    change_request: MCP agent interface (user, 2026-08-20)
    scope: first-time-approval
partition_id: pipeline
name: konspekt/mcp
version: "0.2.0"
boundary_type: api
members:
  - pipeline:CON-003
consumer_compat_policy: semver_per_surface
notes: |
  v0.2.0 — additive: md_path in list_lectures/lecture_status
  (pipeline:DLT-003).
---
```

```yaml
---
id: pipeline:SUR-002
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
name: konspekt/artifact-envelope
version: "0.1.0"
boundary_type: public_storage
members:
  - pipeline:CON-002
consumer_compat_policy: semver_per_surface
---
```

## 6. Requirements

```yaml
---
id: pipeline:REQ-001
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
title: resumability — unchanged stage is skipped on re-run
given: |
  - the work directory contains an artifact for stage S
  - the artifact parses against pipeline:CON-002
  - the artifact's input_fingerprint equals the fingerprint recomputed
    from the current inputs and stage configuration of S
when: user runs `konspekt build` again for the same video and out dir
then: |
  stage S is not executed; its stored artifact is used as input for the
  next stage; the run log records stage S as "skipped (fingerprint
  match)". If the recomputed fingerprint differs, or the artifact is
  absent or fails to parse against pipeline:CON-002, stage S is executed
  and its artifact is rewritten.
negative_cases:
  - artifact present but schema_version differs from the one the current
    binary writes => stage re-executed, artifact rewritten
  - stage configuration changed (model id, language, threshold) =>
    fingerprint differs => stage re-executed
  - "--force-from S passed => S and every later stage re-executed even on
    fingerprint match"
out_of_scope:
  - parallel invocations of `konspekt build` on the same work directory
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
    Given a work dir with a valid stage artifact whose fingerprint
    matches, a second run does not invoke the stage port (observed via a
    counting fake) and produces byte-identical downstream inputs. Given
    a changed stage configuration, the stage port is invoked again.
  test_template: unit
  boundary_classes:
    - fingerprint match => skip
    - fingerprint mismatch (changed config) => re-run
    - artifact missing => run
    - artifact with foreign schema_version => re-run
    - --force-from stage => re-run of that stage and the tail
  failure_scenarios:
    - stage re-executed despite matching fingerprint (wasted API spend)
    - stale artifact reused despite changed configuration
---
```

```yaml
---
id: pipeline:NFR-001
type: NFR
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
title: processing time and cost ceiling for a 2-hour lecture
target:
  - metric: wall_clock_minutes
    threshold: "<= 60"
    environment: |
      macOS arm64, cloud transcription (ElevenLabs), LLM stages through
      the subscription claude-cli provider; the local faster-whisper
      adapter is excluded from this target.
  - metric: external_api_cost_usd
    threshold: "<= 5"
    environment: |
      same run; counts real money paid to external APIs (transcription;
      Anthropic API only when --llm-provider api). Nominal claude-cli
      cost reported by the subscription binary is a budget-guard
      number, not spend, and is excluded.
verification_obligation:
  verification_stage: perf_lab
  artefact: docs/nfr-001-probe.md
applicability:
  invariant_to_all_axes: true
test_obligation:
  predicate: |
    One full `konspekt build` on the 2-hour reference lecture completes
    with exit 0 in at most 60 minutes wall clock with real external API
    spend of at most 5 USD. Recorded manually per the protocol in
    docs/nfr-001-probe.md.
  test_template: perf
  boundary_classes:
    - 2-hour reference lecture, warm cache absent
  failure_scenarios:
    - runaway web_search loops inflating cost
    - transcription polling stall inflating wall clock
---
```

## 7. Data contracts

```yaml
---
id: pipeline:CON-001
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
title: konspekt CLI contract
surface_ref: pipeline:SUR-001
schema:
  binary: konspekt
  subcommand: build
  positional:
    - name: video
      values: "path to an existing video file readable by ffmpeg"
  flags:
    - name: --out
      alias: -o
      values: "<directory>"
      default: ./out
    - name: --lang
      values: [auto, ru, en]
      default: auto
    - name: --force-from
      values: [ingest, transcription, visual, segmentation, factcheck, notes, quiz, compose]
      default: "<absent — no forced re-run>"
    - name: --max-llm-usd
      values: "<positive decimal>"
      default: "15"
    - name: --llm-provider
      values: [claude-cli, api]
      default: claude-cli
    - name: --transcriber
      values: [elevenlabs, whisper]
      default: elevenlabs
    - name: --commons-candidates
      values: "<positive integer>"
      default: "6"
    - name: --generated-images / --no-generated-images
      values: "boolean switch"
      default: disabled
preconditions:
  - "credentials required by the SELECTED adapters are available:
    ELEVENLABS_API_KEY env var when --transcriber elevenlabs;
    ANTHROPIC_API_KEY env var when --llm-provider api; an authenticated
    claude binary on PATH when --llm-provider claude-cli (subscription
    login is managed by Claude Code itself, no env key); EXA_API_KEY
    env var for every build (claim verification searches through
    analysis:EXT-014)"
postconditions:
  - exit 0 => <out>/<lecture-slug>/konspekt.pdf exists and every stage
    artifact in the work directory parses against pipeline:CON-002
  - exit 1 => runtime failure (external API error, budget exceeded);
    artifacts of completed stages remain on disk
  - exit 2 => invalid invocation (missing video file, unknown flag,
    unreadable input, missing credential for a selected adapter,
    missing EXA_API_KEY, `claude` binary absent while --llm-provider
    claude-cli); no stage executed
external_identifiers:
  - subcommand "build"
  - flags --out, --lang, --force-from, --max-llm-usd, --llm-provider,
    --transcriber
  - env vars ELEVENLABS_API_KEY, ANTHROPIC_API_KEY, EXA_API_KEY
compatibility_rules:
  - removing a flag or narrowing its value set => major bump on SUR-001
  - adding a flag with a default => minor bump on SUR-001
error_taxonomy:
  - "exit 0 — success"
  - "exit 1 — runtime failure: external API, budget exceeded (BUDGET_EXCEEDED)"
  - "exit 2 — invalid invocation or configuration"
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
    Argv parser accepts the documented flags and values; a missing video
    file exits 2 before any stage executes; unknown flags exit 2; a
    happy-path run over fake ports exits 0 and leaves a PDF path plus
    valid artifacts.
  test_template: integration
  boundary_classes:
    - happy path over fakes
    - missing video file
    - unknown flag
    - missing required env key
    - missing EXA_API_KEY
  failure_scenarios:
    - stage executed despite invalid invocation
    - exit 0 without a PDF on disk
---
```

```yaml
---
id: pipeline:CON-002
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
title: stage artifact envelope
surface_ref: pipeline:SUR-002
schema:
  format: JSON object, UTF-8, one file per stage
  fields:
    - name: schema_version
      type: integer
      note: version of the payload schema for this stage; starts at 1
    - name: stage
      type: enum
      values: [ingest, transcription, visual, segmentation, factcheck, notes, quiz, compose]
    - name: input_fingerprint
      type: string
      note: sha256 hex, 64 lowercase hex chars, per Glossary definition
    - name: created_at
      type: string
      note: ISO 8601 UTC timestamp of artifact creation
    - name: payload
      type: object
      note: stage-specific content, owned by the stage's partition
  file_name: "NN-<stage>.json where NN is the two-digit stage ordinal 01..08"
preconditions:
  - the work directory exists and is writable
postconditions:
  - every artifact written by any stage parses against this envelope
  - an artifact whose schema_version differs from the version the
    current binary writes for that stage is treated as absent by
    pipeline:REQ-001
external_identifiers:
  - field names schema_version, stage, input_fingerprint, created_at, payload
  - artifact file names 01-ingest.json .. 08-compose.json
compatibility_rules:
  - renaming or removing an envelope field => major bump on SUR-002
  - adding an optional envelope field => minor bump on SUR-002
error_taxonomy:
  - "parse failure => artifact treated as absent (pipeline:REQ-001); no crash"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: "wall_clock:unbounded_skew_created_at_is_informational"
data_scope: all_data
policy_refs:
  - pipeline:POL-001
test_obligation:
  predicate: |
    Envelope round-trips through serde without loss; a JSON object with
    a missing field or a non-enum stage is rejected; a rejected artifact
    is reported as absent to the resumability logic.
  test_template: unit
  boundary_classes:
    - round-trip of every stage value
    - missing field
    - foreign schema_version
    - malformed JSON
  failure_scenarios:
    - malformed artifact crashes the run instead of triggering re-run
---
```

### MCP contract

```yaml
---
id: pipeline:CON-003
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T09:05:45.017Z
    change_request: MCP agent interface (user, 2026-08-20)
    scope: first-time-approval
partition_id: pipeline
title: konspekt MCP server tools
surface_ref: pipeline:SUR-003
schema:
  transport: MCP over stdio (entry point `konspekt-mcp`)
  tools:
    - name: list_lectures
      params: "out_dir (default ./out)"
      returns: "array of {slug, stages_done[], pdf_path|null, quiz_path|null,
        md_path|null}"
    - name: lecture_status
      params: "slug, out_dir"
      returns: "{slug, stages: {stage: done bool}, pdf_path|null, quiz_path|null,
        md_path|null}"
    - name: start_build
      params: "video_path, out_dir, lang, force_from, max_llm_usd"
      returns: "{slug, log_path, pid} — the pipeline runs detached; progress
        is observed via lecture_status and the log file"
    - name: get_outline
      params: "slug, out_dir"
      returns: "{lecture_title, sections: [{section_id, title, start_seconds,
        end_seconds, subsections: [...]}]} from the notes artifact when
        present, otherwise from the segmentation plan"
    - name: get_section
      params: "slug, section_id, out_dir"
      returns: "{section_id, title, source_spans, blocks[]} for a section or
        subsection of the notes artifact"
    - name: get_cut_log
      params: "slug, out_dir"
      returns: "array of {start_seconds, end_seconds, label, reason}"
    - name: get_claims
      params: "slug, out_dir, verdict (optional filter)"
      returns: "array of claims per analysis:CON-021 payload"
    - name: get_quiz
      params: "slug, out_dir"
      returns: "the quiz export object per output:CON-031"
preconditions:
  - artifacts referenced by a reader tool exist in the lecture work
    directory; a missing artifact yields a typed tool error naming the
    missing stage, never a crash
postconditions:
  - reader tools are read-only on the filesystem
  - start_build never blocks the MCP session for the run duration
external_identifiers:
  - entry point konspekt-mcp
  - tool names list_lectures, lecture_status, start_build, get_outline,
    get_section, get_cut_log, get_claims, get_quiz
compatibility_rules:
  - removing a tool or a returned field => major bump on SUR-003
  - adding a tool or an optional field => minor bump on SUR-003
error_taxonomy:
  - "unknown slug or section_id => typed tool error naming the id"
  - "missing artifact => typed tool error naming the stage to run"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:artifact_files"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
test_obligation:
  predicate: |
    Reader functions over a fixture work directory return the
    documented shapes; unknown slug/section and missing artifacts raise
    typed errors naming the culprit; the MCP tool layer delegates to
    the readers one-to-one; start_build spawns a detached process and
    returns slug and log path without waiting for completion.
  test_template: unit
  boundary_classes:
    - each reader over fixtures
    - unknown slug / section => typed error
    - missing artifact => typed error naming the stage
    - start_build detached spawn (fake spawner)
  failure_scenarios:
    - reader mutating the work directory
    - start_build blocking until pipeline completion
---
```

## 8. Invariants

None.

## 9. External dependencies

None. External providers are owned by `extraction`, `analysis` and
`output` partitions.

## 10. Generated artifacts

None.

## 11. Localization

None. Artifact field names and CLI identifiers are English-only
identifiers; lecture-language text lives inside stage payloads owned by
other partitions.

## 12. Policies

```yaml
---
id: pipeline:POL-001
type: Policy
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
title: secrets come from environment variables and never leak
policy_kind: secret_handling
applicability:
  applies_to: every Behavior and Contract of every partition of konspekt
predicate: |
  API keys are read exclusively from environment variables
  (ELEVENLABS_API_KEY, ANTHROPIC_API_KEY). No secret value is written to
  any artifact, log line, PDF, or exception message. Configuration files
  and CLI flags MUST NOT accept secret values.
negative_test_obligations:
  - run the pipeline over fakes with a sentinel key value in the
    environment; assert the sentinel string is absent from every file in
    the out directory and from captured logs
test_obligation:
  predicate: |
    With ELEVENLABS_API_KEY and ANTHROPIC_API_KEY set to sentinel
    values, a full run over fake ports produces no file or captured log
    containing either sentinel.
  test_template: integration
  boundary_classes:
    - full run over fakes with sentinel keys
  failure_scenarios:
    - key echoed into an artifact payload or error message
---
```

```yaml
---
id: pipeline:POL-002
type: Policy
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
title: LLM spend budget per run
policy_kind: rate_limit
applicability:
  applies_to: every Behavior of the analysis partition and every stage
    that calls a paid LLM or transcription API
predicate: |
  Before each paid API call the orchestrator compares accumulated
  estimated spend against max_llm_usd (pipeline:CON-001). When the next
  call would exceed the budget, the run aborts with typed error
  BUDGET_EXCEEDED and exit code 1; artifacts of completed stages remain
  on disk. Web search tool use is capped via the provider's max_uses
  parameter on every request that enables it.
negative_test_obligations:
  - configure a budget lower than the cost of the next fake call; assert
    the run stops with BUDGET_EXCEEDED, exit 1, and completed artifacts
    survive
test_obligation:
  predicate: |
    A run whose fake LLM port reports per-call cost above the remaining
    budget aborts with BUDGET_EXCEEDED before invoking the port, exits
    1, and keeps earlier artifacts intact.
  test_template: unit
  boundary_classes:
    - budget hit exactly at the boundary
    - budget exceeded before first call
  failure_scenarios:
    - paid call issued after the budget is exhausted
---
```

## 13. Constraints

```yaml
---
id: pipeline:CST-001
type: Constraint
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
constraint: "Python runtime >= 3.12 (pyproject requires-python = \">=3.12\")"
rationale: |
  The media/ML dependency set (faster-whisper, pillow, typst bindings)
  publishes wheels for CPython 3.12+ on macOS arm64, and the user's
  toolchain (uv) targets 3.12+.
test_obligation:
  predicate: |
    pyproject.toml#project.requires-python equals ">=3.12" verbatim.
  test_template: contract
  boundary_classes:
    - canonical pyproject.toml
  failure_scenarios:
    - requires-python missing or lowered below 3.12
---
```

## 14. Migrations

None. Greenfield project; no data at rest predates this spec.

## 15. Deltas

```yaml
---
id: pipeline:DLT-002
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T08:52:43.869Z
    change_request: NFR recalibration after reference measurement (user-approved polish round, 2026-08-20)
    scope: first-time-approval
partition_id: pipeline
target_id: pipeline:NFR-001
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  NFR targets recalibrated after the reference measurement on the
  2 h 14 min lecture (2026-08-20): wall clock <= 60 minutes (measured
  ~50 for a clean run: transcription ~13, segmentation ~16, sectioned
  notes ~15); the cost metric becomes external_api_cost_usd <= 5 (real
  spend, measured ~0.6 for transcription) because LLM stages moved to
  the subscription claude-cli provider whose nominal cost figure is a
  budget guard, not money.
tests_old_behavior:
  - not_applicable: manual_probe_thresholds_replaced_before_release
tests_new_behavior:
  - tests/pipeline/test_project_constraints.py (protocol pins the new
    thresholds)
---
```

```yaml
---
id: pipeline:DLT-003
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T17:48:22.567Z
    change_request: agent-facing Markdown bundle (user request 2026-08-22, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: pipeline
target_id: pipeline:CON-003
kind: extend
compatibility_action: ignore
baseline_version: c842112
summary: |
  list_lectures and lecture_status gain the optional field md_path (the
  bundle entry point <out>/<slug>/md/README.md per output:CON-032, null
  until a run completes). Minor bump of SUR-003 to 0.2.0.
tests_old_behavior:
  - tests/pipeline/test_artifacts_query.py (existing fields unchanged)
tests_new_behavior:
  - tests/pipeline/test_artifacts_query.py (md_path present/null)
---
```

```yaml
---
id: pipeline:DLT-004
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-24T18:29:57.914Z
    change_request: source-first illustration selection, generation behind a flag (user decision 2026-08-24, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: pipeline
target_id: pipeline:CON-001
kind: extend
compatibility_action: ignore
baseline_version: 33e5d88
summary: |
  Two illustration flags on `konspekt build`: --commons-candidates
  (positive integer, default 6) — how many Wikimedia Commons search
  results are graded per illustration request; --generated-images /
  --no-generated-images (default disabled) — whether image generation
  may fill requests that have no perfect Commons candidate
  (analysis:DLT-029). Minor bump of SUR-001 to 0.3.0.
tests_old_behavior:
  - tests/pipeline/test_cli.py (existing flags unchanged)
tests_new_behavior:
  - tests/pipeline/test_cli.py, tests/pipeline/test_orchestrator.py
    (defaults and pass-through into the notes stage config)
---
```

```yaml
---
id: pipeline:DLT-005
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:14:57.869Z
    change_request: Exa evidence-first fact-check (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: pipeline
target_id: pipeline:CON-001
kind: extend
compatibility_action: reject
baseline_version: 734063e
summary: |
  EXA_API_KEY becomes a required credential for every build, because
  claim verification always searches through analysis:EXT-014. A
  missing key exits 2 before any stage runs. Invocations that worked
  without the key now fail fast => pipeline:SUR-001 0.4.0 (breaking,
  pre-1.0).
tests_old_behavior:
  - tests/pipeline/test_cli.py (documented flags and exit codes
    unchanged)
tests_new_behavior:
  - tests/pipeline/test_cli.py (missing EXA_API_KEY => exit 2, no stage
    executed)
---
```

```yaml
---
id: pipeline:DLT-001
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T20:35:09.906Z
    change_request: switch LLM stages to subscription claude CLI per user instruction 2026-08-19
    scope: first-time-approval
partition_id: pipeline
target_id: pipeline:CON-001
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  Additive revision of the CLI contract: provider selection flags
  --llm-provider (default claude-cli, running LLM stages through the
  authenticated Claude Code binary under the user's subscription) and
  --transcriber (default elevenlabs, alternative whisper without an API
  key). Credential preconditions become conditional on the selected
  adapters. Invocations valid under v0.1.0 keep the same behavior
  (defaults preserve the CLI shape; provider default moves LLM calls to
  the subscription channel on the user's explicit instruction,
  2026-08-19).
tests_old_behavior:
  - tests/pipeline/test_cli.py (v0.1.0 argv shapes stay green unchanged)
tests_new_behavior:
  - tests/pipeline/test_cli.py (provider flags, conditional env checks)
---
```

## 16. Implementation bindings

None yet. Bindings are added when operationally needed (test probes).

## 17. Open questions

None.

## 18. Assumptions

```yaml
---
id: pipeline:ASM-001
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.197Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: pipeline
assumption: |
  MVP spec approvals are recorded with approver_identity "cyberash" on
  the user's explicit standing instruction given in the planning session
  on 2026-08-19 ("Спеку пока можешь подтверждать сам, т.к. это MVP").
blocking: no
review_by: 2026-10-01
default_if_unresolved: keep_assumption
tests:
  - not_applicable: process_assumption_no_runtime_behavior
partition_id_note: applies to every partition of this repository
---
```

## 19. Out of scope

- Web service or GUI wrapper (CLI only for MVP).
- Parallel processing of multiple lectures in one invocation.
- Gemini video understanding adapter (deferred alternative for the
  visual stage; owned by `extraction` when introduced).
- Editing or re-rendering the source video.
