# `konspekt` — Partition `extraction`

> Media intake: audio extraction, speech transcription, key-frame
> extraction with dedupe and OCR. Produces the artifacts consumed by the
> `analysis` partition.

---

## 1. Context

The extraction partition owns pipeline stages 1-3: `ingest` (split the
video into a normalized audio track plus media metadata), `transcription`
(speech to timestamped text with speakers), and `visual` (candidate
frames with perceptual hashes and OCR text). Transcription runs through
a port with two adapters: ElevenLabs Scribe v2 (default, cloud) and
faster-whisper (local, optional extra). Frame extraction combines ffmpeg
scene detection with fixed-interval sampling so that lectures without
slide transitions (whiteboard, talking head) still yield frames.

## 2. Glossary

- **Segment** — one utterance of the transcript with start/end seconds,
  text, and an optional speaker label.
- **Candidate frame** — a JPEG extracted from the video at a known
  timestamp, before dedupe.
- **dHash** — 64-bit difference hash of a frame, hex-encoded, computed
  on a 9x8 grayscale downscale.
- **Duplicate frames** — two frames whose dHash Hamming distance is
  strictly below the dedupe threshold from stage configuration.
- **Sampling interval** — the fixed period, in seconds, at which frames
  are captured in addition to scene-change frames.

## 3. Partition

```yaml
---
id: extraction
type: Partition
partition_id: extraction
owner_team: cyberash
gate_scope:
  - extraction
dependencies_on_other_partitions:
  - pipeline:SUR-002@0.1.0
  - pipeline:POL-001@1
default_policy_set:
  - pipeline:POL-001
id_namespace: extraction
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
id: extraction:SUR-010
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
name: konspekt/extraction-artifacts
version: "0.2.0"
boundary_type: public_storage
members:
  - extraction:CON-010
  - extraction:CON-011
  - extraction:CON-012
consumer_compat_policy: semver_per_surface
notes: |
  v0.2.0 — additive: frames.json gains content_box (extraction:DLT-011).
  v0.1.0 — original extraction artifacts.
---
```

## 6. Requirements

```yaml
---
id: extraction:REQ-010
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
title: language autodetection for --lang auto
given: |
  - a lecture audio track in Russian or English
  - CLI invoked with --lang auto (pipeline:CON-001)
when: the transcription stage runs
then: |
  the transcript artifact records language "ru" for Russian speech and
  "en" for English speech, taken from the transcription provider's
  detection; with --lang ru or --lang en the given code is passed to the
  provider and recorded verbatim in the artifact.
negative_cases:
  - provider returns a language outside {ru, en} => recorded verbatim;
    the run continues (downstream prompts receive the detected code)
out_of_scope:
  - per-segment language switching within one lecture
applicability:
  axis: language
  values: [auto, ru, en]
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: "at_least_once_with_key:input_fingerprint"
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
test_obligation:
  predicate: |
    With a fake transcription port reporting language "ru", the stored
    transcript artifact carries language "ru"; with --lang en the port
    receives language_hint "en" and the artifact carries "en".
  test_template: unit
  boundary_classes:
    - auto with ru detection
    - auto with en detection
    - explicit ru, explicit en
  failure_scenarios:
    - artifact language differs from provider detection
---
```

```yaml
---
id: extraction:REQ-011
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:00.789Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: extraction
title: frames are cropped to the detected content region
given: |
  - a lecture video whose screen layout carries a slide/board content
    area plus platform chrome (speaker camera, chat, toolbars)
  - the visual stage about to capture candidate frames
when: the visual stage runs
then: |
  probe frames are sampled evenly across the video (count per
  extraction:ASM-011) and handed to the layout detection port, which
  returns the content region as a pixel box; when the box lies inside
  the frame and covers at least the minimum area share
  (extraction:ASM-011), every captured frame is cropped to that box
  before hashing and OCR, and the frames artifact records the box as
  content_box (extraction:CON-012). Scene detection runs on the cropped
  picture, so chrome changes (chat messages, camera) do not produce
  candidate frames.
negative_cases:
  - detection port returns no box, a box outside the frame or below the
    minimum area share => frames are stored uncropped, content_box is
    null, the run continues and the reason is logged
  - detection port raises => same as no box (the visual stage never
    fails because of layout detection)
out_of_scope:
  - per-frame dynamic layouts (the box is detected once per video)
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
test_obligation:
  predicate: |
    With a fake layout port returning a valid box, the capture port
    receives that box and the artifact carries content_box; with a box
    below the minimum area share or outside the frame, or with a port
    failure, capture receives no box and content_box is null while the
    frames are still produced.
  test_template: unit
  boundary_classes:
    - valid box applied
    - box below minimum area share => uncropped
    - box outside the frame => uncropped
    - port failure => uncropped, run continues
  failure_scenarios:
    - visual stage failing because layout detection failed
    - content_box recorded while frames were stored uncropped
---
```

## 7. Data contracts

```yaml
---
id: extraction:CON-010
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
title: media.json payload (ingest artifact)
surface_ref: extraction:SUR-010
schema:
  envelope: pipeline:CON-002 with stage "ingest"
  payload_fields:
    - name: video_path
      type: string
    - name: audio_path
      type: string
      note: path to the extracted mono 16 kHz Opus audio (OGG container,
        32 kbit/s) — sized for reliable upload to the cloud transcriber
        (a 2-hour lecture is ~30 MB versus ~230 MB as FLAC)
    - name: duration_seconds
      type: number
      note: container duration from ffprobe, > 0
preconditions:
  - the video file exists and ffprobe reports a duration
postconditions:
  - audio_path points to an existing OGG/Opus file
external_identifiers:
  - payload field names video_path, audio_path, duration_seconds
compatibility_rules:
  - renaming or removing a payload field => major bump on SUR-010
  - adding an optional payload field => minor bump on SUR-010
error_taxonomy:
  - "unreadable video => stage fails, run exits 1 (pipeline:CON-001)"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: none
data_scope: all_data
policy_refs:
  - pipeline:POL-001
test_obligation:
  predicate: |
    Payload round-trips through serde; duration_seconds <= 0 or a
    missing field is rejected.
  test_template: unit
  boundary_classes:
    - valid payload round-trip
    - missing field
    - non-positive duration
  failure_scenarios:
    - silently accepting a payload without audio_path
---
```

```yaml
---
id: extraction:CON-011
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
title: transcript.json payload (transcription artifact)
surface_ref: extraction:SUR-010
schema:
  envelope: pipeline:CON-002 with stage "transcription"
  payload_fields:
    - name: language
      type: string
      note: BCP-47 primary subtag as reported per extraction:REQ-010
    - name: segments
      type: array
      items:
        - name: start_seconds
          type: number
        - name: end_seconds
          type: number
          note: ">= start_seconds"
        - name: text
          type: string
          note: non-empty after trimming
        - name: speaker
          type: "string | null"
preconditions:
  - the ingest artifact (extraction:CON-010) exists
postconditions:
  - segments are ordered by start_seconds ascending
  - provider timestamps in milliseconds are converted to seconds without
    precision loss beyond 1 ms
external_identifiers:
  - payload field names language, segments, start_seconds, end_seconds,
    text, speaker
compatibility_rules:
  - renaming or removing a payload field => major bump on SUR-010
  - adding an optional payload field => minor bump on SUR-010
error_taxonomy:
  - "provider job failure => stage fails, run exits 1"
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
test_obligation:
  predicate: |
    A fixture payload round-trips; out-of-order segments are rejected;
    a provider response with millisecond timestamps maps to seconds with
    at most 1 ms deviation; empty-text segments are dropped by the
    adapter mapping.
  test_template: unit
  boundary_classes:
    - valid round-trip
    - out-of-order segments
    - ms-to-seconds mapping
    - empty-text utterance dropped
  failure_scenarios:
    - segment ordering violated in stored artifact
---
```

```yaml
---
id: extraction:CON-012
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
title: frames.json payload (visual artifact)
surface_ref: extraction:SUR-010
schema:
  envelope: pipeline:CON-002 with stage "visual"
  payload_fields:
    - name: frames
      type: array
      items:
        - name: timestamp_seconds
          type: number
        - name: image_path
          type: string
          note: JPEG under the work directory, relative path
        - name: dhash
          type: string
          note: 16 lowercase hex chars (64-bit dHash)
        - name: ocr_text
          type: "string | null"
          note: tesseract output, null when OCR is unavailable
    - name: content_box
      type: "object | null"
      note: "detected lecture content region in source pixels
        {x, y, width, height}; every stored frame is cropped to it;
        null when no crop was applied (extraction:REQ-011)"
preconditions:
  - the ingest artifact (extraction:CON-010) exists
postconditions:
  - frames are ordered by timestamp_seconds ascending
  - the frame set satisfies extraction:INV-010
external_identifiers:
  - payload field names frames, timestamp_seconds, image_path, dhash,
    ocr_text, content_box
compatibility_rules:
  - renaming or removing a payload field => major bump on SUR-010
  - adding an optional payload field => minor bump on SUR-010
error_taxonomy:
  - "ffmpeg failure => stage fails, run exits 1"
  - "tesseract absent => ocr_text is null for every frame; run continues"
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
test_obligation:
  predicate: |
    A fixture payload round-trips; a dhash value that is not 16 hex
    chars is rejected; missing image file at image_path is reported at
    compose time, not silently skipped.
  test_template: unit
  boundary_classes:
    - valid round-trip
    - malformed dhash
    - ocr_text null
  failure_scenarios:
    - frame entry pointing at a non-existent image accepted silently
---
```

## 8. Invariants

```yaml
---
id: extraction:INV-010
type: Invariant
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
title: stored frames are deduplicated by perceptual hash
always: |
  In every stored frames.json payload, for every pair of frame entries
  (a, b) with a != b, hamming_distance(a.dhash, b.dhash) >= the dedupe
  threshold from stage configuration (default per extraction:ASM-010).
scope: konspekt/extraction-artifacts
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
  - two near-identical slide frames captured by interval sampling MUST
    collapse into one entry (the earlier timestamp wins)
out_of_scope:
  - semantic duplicates with different dHash (animated slide builds)
test_obligation:
  predicate: |
    Feeding the dedupe function synthetic frames with Hamming distances
    below, at, and above the threshold yields a set where no pair is
    below the threshold, and the earliest timestamp of each collapsed
    group is kept.
  test_template: unit
  boundary_classes:
    - distance below threshold => collapsed
    - distance exactly at threshold => kept
    - distance above threshold => kept
  failure_scenarios:
    - later duplicate kept instead of the earliest
---
```

## 9. External dependencies

```yaml
---
id: extraction:EXT-001
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
provider: ElevenLabs Speech-to-Text (Scribe)
provider_surface: "elevenlabs-api@v1 (POST /v1/speech-to-text, model scribe_v2)"
authority_url_or_doc: "https://elevenlabs.io/docs/api-reference/speech-to-text"
consumer_contract:
  request:
    - multipart upload of the FLAC audio file
    - model_id "scribe_v2"
    - diarize true
    - language_code passed when --lang is ru or en, omitted for auto
  response_expectations:
    - language_code string
    - words array with start/end seconds, text, speaker_id
    - utterance grouping derivable from speaker_id transitions
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-19
auth_scope:
  - api key via env var ELEVENLABS_API_KEY (header xi-api-key)
rate_limits:
  - provider-side concurrency limits by plan tier; one request per run
retry/idempotency:
  - one retry on HTTP 5xx and on transport failures (connection reset,
    timeout); the upload is idempotent (same file, same parameters, no
    server-side state we depend on)
error_taxonomy:
  - HTTP 401 => missing/invalid key => run exits 2
  - HTTP 5xx or transport failure after retry => run exits 1
sandbox_or_fixture:
  - tests use recorded response fixtures; no live calls in CI
test_obligation:
  predicate: |
    The adapter maps a recorded Scribe response fixture into
    extraction:CON-011 segments: word timestamps grouped into
    speaker-turn segments, language_code propagated.
  test_template: contract
  boundary_classes:
    - ru fixture
    - en fixture
    - single-speaker fixture (null speaker labels)
  failure_scenarios:
    - speaker turns merged across different speaker_ids
---
```

```yaml
---
id: extraction:EXT-002
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
provider: ffmpeg / ffprobe (cli binaries)
provider_surface: "ffmpeg@>=6"
authority_url_or_doc: "https://ffmpeg.org/documentation.html"
consumer_contract:
  invocations:
    - cmd: "ffprobe -v error -show_entries format=duration -of json <video>"
      expects:
        - exit 0; stdout JSON with format.duration
    - cmd: "ffmpeg -y -i <video> -vn -ac 1 -ar 16000 -c:a libopus -b:a 32k <audio.ogg>"
      expects:
        - exit 0; OGG/Opus file written
    - cmd: "ffmpeg scene-detection and fps sampling filters producing JPEG frames"
      expects:
        - exit 0; one JPEG per selected frame with known timestamps
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-19
auth_scope:
  not_applicable: local_binary_no_auth
  reason: local binary operating on local files
rate_limits:
  not_applicable: local_binary_no_rate_limit
  reason: local binary
retry/idempotency:
  not_applicable: deterministic_local_reruns
  reason: failed invocations fail the stage; re-run is safe
error_taxonomy:
  - non-zero exit => stage fails with stderr in the error message; run
    exits 1
sandbox_or_fixture:
  - integration tests generate tiny synthetic videos with ffmpeg itself
test_obligation:
  predicate: |
    On a synthetic 5-second test video the ingest adapter produces a
    FLAC file and a positive duration; a non-existent input raises an
    error carrying ffmpeg stderr.
  test_template: integration
  boundary_classes:
    - synthetic video happy path
    - missing input file
  failure_scenarios:
    - silent success with empty audio output
---
```

```yaml
---
id: extraction:EXT-003
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
provider: faster-whisper (python package, local model)
provider_surface: "faster-whisper@>=1.1 (WhisperModel.transcribe)"
authority_url_or_doc: "https://github.com/SYSTRAN/faster-whisper"
consumer_contract:
  request:
    - WhisperModel(model_size).transcribe(audio_path, language=hint_or_none, vad_filter=true)
  response_expectations:
    - iterable of segments with start, end, text
    - info.language for autodetection
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-19
auth_scope:
  not_applicable: local_model_no_auth
  reason: local inference, no network
rate_limits:
  not_applicable: local_model_no_rate_limit
  reason: local inference
retry/idempotency:
  not_applicable: deterministic_local_reruns
  reason: re-running transcription locally is safe
error_taxonomy:
  - package not installed => stage fails with an actionable message
    naming the "local-whisper" extra; run exits 2
sandbox_or_fixture:
  - unit tests exercise the mapping with stand-in segment objects; no
    model download in CI
test_obligation:
  predicate: |
    The adapter maps stand-in faster-whisper segments into
    extraction:CON-011 segments with speaker null and propagates
    info.language.
  test_template: contract
  boundary_classes:
    - segments mapping
    - language propagation
  failure_scenarios:
    - speaker fabricated for a provider without diarization
---
```

```yaml
---
id: extraction:EXT-004
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
provider: tesseract (cli binary)
provider_surface: "tesseract@>=5 (CLI, rus+eng traineddata)"
authority_url_or_doc: "https://tesseract-ocr.github.io/"
consumer_contract:
  invocations:
    - cmd: "tesseract <frame.jpg> stdout -l rus+eng"
      expects:
        - exit 0; recognized text on stdout (empty output is valid)
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-19
auth_scope:
  not_applicable: local_binary_no_auth
  reason: local binary
rate_limits:
  not_applicable: local_binary_no_rate_limit
  reason: local binary
retry/idempotency:
  not_applicable: deterministic_local_reruns
  reason: re-running OCR is safe
error_taxonomy:
  - binary absent => ocr_text null for every frame; run continues
    (extraction:CON-012 error_taxonomy)
sandbox_or_fixture:
  - unit tests render a synthetic text image with Pillow and OCR it when
    tesseract is present; the test is skipped with an explicit reason
    when the binary is absent
test_obligation:
  predicate: |
    A synthetic image with the string "KONSPEKT 42" yields ocr_text
    containing "KONSPEKT"; with the binary absent the port returns null
    without raising.
  test_template: integration
  boundary_classes:
    - text image
    - binary absent
  failure_scenarios:
    - OCR failure aborting the visual stage
---
```

```yaml
---
id: extraction:EXT-005
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:00.845Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: extraction
provider: Claude Code CLI (subscription-authenticated local binary), vision use for layout detection
provider_surface: "claude-code-cli@>=2.1 (claude -p --output-format json --allowedTools Read)"
authority_url_or_doc: "https://code.claude.com/docs/en/cli-reference"
consumer_contract:
  invocations:
    - cmd: "claude -p --output-format json --model <model> --allowedTools Read"
      stdin: prompt naming the probe frame paths and the frame pixel
        size, asking for the content region as one JSON object
        {x, y, width, height} in source pixels
      expects:
        - exit 0; result parses as that JSON object with non-negative
          integers
        - any other shape => treated as "no box" (extraction:REQ-011)
  authentication: managed by Claude Code itself; no API key enters the
    pipeline environment
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-08-22
auth_scope:
  not_applicable: cli_manages_own_login
  reason: the binary holds the user's subscription session
rate_limits:
  - one invocation per lecture
retry/idempotency:
  - no retry; a failed or malformed answer means uncropped frames
error_taxonomy:
  - binary absent, non-zero exit, is_error or malformed result => no
    box; visual stage continues uncropped
sandbox_or_fixture:
  - unit tests inject a fake runner; no live invocations in CI
test_obligation:
  predicate: |
    The CLI layout adapter over a fake runner parses a valid box from
    the result text, charges the budget with total_cost_usd and returns
    None for malformed output or a runner error.
  test_template: contract
  boundary_classes:
    - valid box parsed
    - malformed result => None
    - runner error => None
  failure_scenarios:
    - adapter raising out of the visual stage on a malformed answer
---
```

## 10. Generated artifacts

None.

## 11. Localization

None. Payload text carries the lecture's own language; field names are
English identifiers covered by extraction:SUR-010.

## 12. Policies

None owned by this partition. `default_policy_set` applies
`pipeline:POL-001` to every boundary contract above.

## 13. Constraints

None.

## 14. Migrations

None.

## 15. Deltas

```yaml
---
id: extraction:DLT-010
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-20T05:24:37.851Z
    change_request: "full-lecture run failure: oversized FLAC upload (2026-08-20)"
    scope: first-time-approval
partition_id: extraction
target_id: extraction:CON-010
kind: replace
compatibility_action: ignore
baseline_version: a3b7f19
summary: |
  Extracted audio switches from FLAC to Opus (OGG, mono, 16 kHz,
  32 kbit/s): the 230 MB FLAC of a 2-hour lecture broke the upload to
  the transcription provider (connection reset) and dominated wall
  clock; Opus is ~8x smaller with no practical STT quality loss. The
  transcriber adapter additionally retries transport failures once
  (extraction:EXT-001). Work directories are disposable; no stored
  consumers of the FLAC path exist.
tests_old_behavior:
  - not_applicable: no_released_consumers_of_flac_audio
tests_new_behavior:
  - tests/features/ingest (OGG/Opus extraction on the synthetic video)
  - tests/features/transcription (transport-failure retry)
---
```

```yaml
---
id: extraction:DLT-011
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:00.966Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: extraction
target_id: extraction:CON-012
kind: extend
compatibility_action: ignore
baseline_version: 3fd094a
summary: |
  Frames are cropped to the lecture content region detected once per
  video (extraction:REQ-011). The frames.json payload gains the optional
  field content_box {x, y, width, height} (null when no crop was
  applied); existing consumers ignore it. Minor bump of SUR-010 to
  0.2.0.
tests_old_behavior:
  - tests/features/visual (payload without content_box still parses)
tests_new_behavior:
  - tests/features/visual (content_box round-trip, crop applied to
    capture, fallbacks of extraction:REQ-011)
---
```

## 16. Implementation bindings

None yet.

## 17. Open questions

None.

## 18. Assumptions

```yaml
---
id: extraction:ASM-010
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-19T19:58:25.255Z
    change_request: MVP spec v0.1.0 — approval delegated by user in planning session 2026-08-19 (plan proud-sleeping-globe)
    scope: first-time-approval
partition_id: extraction
assumption: |
  Default visual-stage configuration: sampling interval 25 seconds,
  scene-detection threshold 0.20, dHash dedupe threshold 10 (Hamming
  distance on 64-bit hashes). Values are tuned on the reference lectures
  during milestone M3 acceptance.
blocking: no
review_by: 2026-10-01
default_if_unresolved: keep_assumption
tests:
  - tests/features/visual (dedupe threshold boundary tests reference the
    configured value, not a literal)
---
```

```yaml
---
id: extraction:ASM-011
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-08-22T14:10:00.905Z
    change_request: "M4 visuals and structuring: crop, illustrations, tables/diagrams/charts (user request 2026-08-22, approval delegated per pipeline:ASM-001)"
    scope: first-time-approval
partition_id: extraction
assumption: |
  Layout detection defaults: 5 probe frames sampled at 10..90 percent
  of the video duration; a detected content box is accepted only when it
  covers at least 40 percent of the frame area; detection uses the
  segmentation model setting. Values are tuned on the reference
  lectures (MTS Link layout: slide left, camera and chat right).
blocking: no
review_by: 2026-10-15
default_if_unresolved: keep_assumption
tests:
  - tests/features/visual (minimum-area boundary tests reference the
    configured value, not a literal)
---
```

## 19. Out of scope

- Gemini video understanding as an alternative visual adapter (deferred;
  requires a new ExternalDependency record when introduced).
- Per-segment language switching inside one lecture.
- Video editing or clip export.
