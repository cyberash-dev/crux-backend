# `konspekt` — Partition `service`

> Cloud service around the pipeline: a control plane on a dedicated
> Convex deployment exposes a REST API to client applications, runs
> every lecture in its own Daytona sandbox and stores the run results.
> Written per `~/.claude/rules/spec-driven-development.md`.

---

## 1. Context

A client application (the "frontback", Next.js + Convex, developed by
another team) owns users, uploads and UI. It submits a YouTube lecture
URL to this service and later reads the run status and the results. The
service knows no users: it stores runs and their results only. Each run
executes in a fresh Daytona sandbox built from a prebuilt snapshot; the
worker inside downloads the video, runs `konspekt build` and reports
progress and results back to the control plane.

## 2. Glossary

- **Client** — an application holding the service API key; the only
  caller of the `/v1` API.
- **Run** — one processing request for one YouTube video; identified by
  `run_id`.
- **Control plane** — the Convex deployment of this service: HTTP API,
  run documents, result documents, file storage, scheduling.
- **Worker** — the process started inside a run's sandbox; talks to the
  control plane only through the worker API with the run token.
- **Run token** — a random secret minted per run, handed to the worker
  as an environment variable, stored by the control plane only as a
  sha256 hash.
- **Video id** — the 11-character YouTube identifier
  (`[A-Za-z0-9_-]{11}`) extracted from the submitted URL.
- **Exam session** — a chat in which the examiner questions a student
  on the quiz of one succeeded run; identified by `exam_id`.
- **Examiner** — the model-backed agent that grades the student's
  answers and writes the examiner messages of an exam session.
- **Examiner sandbox** — the Daytona sandbox of one exam session that
  runs examiner turns; disposable, the session state lives in the
  control plane.
- **Turn** — one invocation of `konspekt-exam-turn`: the open turn
  produces the first question, a reply turn answers one student message.
- **Mastered** — a quiz question the student answered correctly per
  `service:INV-001`; a session is mastered when all its questions are.

## 3. Partition

```yaml
---
id: service
type: Partition
partition_id: service
owner_team: cyberash
gate_scope:
  - service
dependencies_on_other_partitions:
  - pipeline
  - analysis
  - output
default_policy_set:
  - service:POL-001
  - pipeline:POL-001
id_namespace: service
unmodeled_budget:
  current: 0
  baseline_at: "2026-09-12"
  baseline_value: 0
  trend: monotonic_non_increasing
---
```

## 4. Brownfield baseline

Covered by `pipeline:BL-001` for the Python package; the control plane in
`control-plane/` is greenfield.

## 5. Surfaces

```yaml
---
id: service:SUR-001
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:05.784Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
name: konspekt/service-api
version: "0.3.0"
boundary_type: api
members:
  - service:CON-001
  - service:CON-003
  - service:GEN-001
consumer_compat_policy: semver_per_surface
notes: |
  v0.3.0 — additive: exam sessions with the examiner (service:CON-003,
  service:DLT-002); run endpoints are unchanged.
  v0.2.0 — additive: the OpenAPI description control-plane/openapi.yaml
  is published with the API (service:DLT-001); the API is unchanged.
  v0.1.0 — initial client API: submit a run, read its status, read its
  results.
---
```

```yaml
---
id: service:SUR-002
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:05.842Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
name: konspekt/worker-api
version: "0.1.0"
boundary_type: api
members:
  - service:CON-002
consumer_compat_policy: semver_per_surface
notes: |
  v0.1.0 — sandbox worker to control plane: progress events, file
  uploads, completion.
---
```

```yaml
---
id: service:SUR-003
type: Surface
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.184Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
name: konspekt/examiner-turn
version: "0.1.0"
boundary_type: cli
members:
  - service:CON-004
consumer_compat_policy: semver_per_surface
notes: |
  v0.1.0 — control plane to examiner sandbox: open and reply turns of
  an exam session.
---
```

## 6. Requirements

```yaml
---
id: service:REQ-001
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:05.903Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: a submitted run is processed in its own sandbox and ends in a terminal status
given: |
  - a client submitted a valid YouTube URL through POST /v1/runs
    (service:CON-001)
  - a worker snapshot exists in Daytona (service:EXT-001)
when: the control plane processes the run queue
then: |
  the run moves queued -> provisioning -> running -> succeeded or
  failed. Provisioning creates one sandbox per run from the configured
  snapshot with the outbound proxy, the worker secrets as environment
  variables, auto-stop disabled and a wall-clock TTL of 240 minutes,
  then starts the worker asynchronously. At most MAX_PARALLEL_RUNS runs
  (control-plane env, default 1) are in provisioning or running; the
  others wait in submission order. A run becomes succeeded only when
  the worker's completion carries the full result (service:CON-002),
  which is stored atomically with the status. After a terminal status
  the sandbox is deleted.
negative_cases:
  - sandbox creation or worker start fails => failed with
    SANDBOX_START_FAILED
  - no worker event for 15 minutes while provisioning or running =>
    failed with WORKER_LOST; the sandbox is deleted
  - the worker reports failure => failed with the reported error code
out_of_scope:
  - retrying a failed run; a client submits a new run instead
  - cancelling a run
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: multi_no_shared_mutable
  read_consistency: strong
  idempotency: "at_least_once_with_key:run_id"
  time_source: server_clock
data_scope: all_data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    Over a fake sandbox gateway and a fake clock: a queued run is
    provisioned only while fewer than MAX_PARALLEL_RUNS runs are
    active; a started worker moves the run to running; a success
    completion stores results and deletes the sandbox; a gateway
    failure yields SANDBOX_START_FAILED; a run silent for 15 minutes
    yields WORKER_LOST and its sandbox is deleted.
  test_template: integration
  boundary_classes:
    - queue respects MAX_PARALLEL_RUNS
    - success completion stores results and deletes the sandbox
    - sandbox creation failure
    - silent worker => WORKER_LOST
  failure_scenarios:
    - a run stuck in running forever
    - two sandboxes started for one run
---
```

```yaml
---
id: service:REQ-002
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:05.964Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: the worker downloads the lecture, builds it and reports the result
given: |
  - a sandbox started with KONSPEKT_RUN_ID, KONSPEKT_API_BASE,
    KONSPEKT_RUN_TOKEN, KONSPEKT_YOUTUBE_URL and KONSPEKT_LANG in the
    environment, plus the pipeline credentials
when: the worker entry point konspekt-worker runs
then: |
  the worker reads the video metadata with yt-dlp restricted to the
  YouTube extractor, rejects live, upcoming and non-public videos and
  videos longer than 4 hours, downloads a video stream of at most
  1080p over HTTPS DASH plus the best audio merged into one file through
  the proxy, then runs `konspekt build` on it (pipeline:CON-001). It
  posts a stage_completed event for "download" and for every pipeline
  stage whose artifact appears, and a heartbeat at least every 60
  seconds. On success it uploads konspekt.pdf, konspekt.md and the
  images of the Markdown bundle and posts a success completion with the
  structured result (video metadata, outline, sections, claims, quiz,
  cut log, LLM spend). On failure it posts a failed completion with a
  code: VIDEO_UNAVAILABLE (metadata rejected or unavailable),
  DOWNLOAD_FAILED (download error), CONFIGURATION_ERROR (build exit 2),
  PIPELINE_FAILED (build exit 1).
negative_cases:
  - the control plane rejects the run token => the worker stops without
    running further stages
  - a worker API call fails => retried up to 3 times with 2 s, 4 s,
    8 s pauses before the worker gives up
out_of_scope:
  - resuming a failed run in a new sandbox
  - non-YouTube sources
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: server_clock
data_scope: all_data
policy_refs:
  - service:POL-001
  - pipeline:POL-001
test_obligation:
  predicate: |
    Over a fake video source, a fake build runner and a fake worker API
    transport: a public video yields download and stage events, file
    uploads and a success completion whose result carries sections,
    claims and quiz from the build artifacts; a live or private video
    yields VIDEO_UNAVAILABLE without a download; build exit 2 yields
    CONFIGURATION_ERROR, exit 1 PIPELINE_FAILED; the run token never
    appears in logs or payloads.
  test_template: integration
  boundary_classes:
    - public video success
    - live or private video rejected
    - download failure
    - build exit 1 and exit 2
    - worker API retry then give up
  failure_scenarios:
    - success completion without the result
    - run token leaked into a log line
---
```

```yaml
---
id: service:REQ-003
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.245Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: an exam session questions the student on a succeeded run until every quiz question is mastered
given: |
  - a run with status succeeded (service:REQ-001) whose result holds
    konspekt.md and the quiz
  - an examiner snapshot exists in Daytona (service:EXT-001)
when: a client opens an exam session through POST /v1/runs/{run_id}/exams (service:CON-003)
then: |
  the control plane creates one examiner sandbox for the session from
  EXAMINER_SNAPSHOT, copies the run's konspekt.md and quiz.json into it
  and runs an open turn (service:CON-004). The session is stored with
  status active, its progress and the first examiner message only after
  the open turn succeeds. The first message names the lecture and asks
  the first quiz question with its options lettered A-D, without a
  model call. Every later student message is answered by one examiner
  turn (service:REQ-004). The session becomes mastered when a turn
  reports every question mastered (service:INV-001); POST
  /v1/exams/{exam_id}/close sets an active session closed. After
  mastered or closed the sandbox is deleted. An examiner sandbox stops
  after 15 idle minutes and is deleted when it stops; a turn that finds
  no sandbox creates a new one and copies the materials again before
  running.
negative_cases:
  - the run is not succeeded => 409 RUN_NOT_FINISHED, no session
  - sandbox creation, copying or the open turn fails => 503
    EXAMINER_FAILED, no session stored, the sandbox deleted
out_of_scope:
  - a time limit on a session; an active session stays active until
    mastered or closed
  - student identity; the client maps exam ids to its users
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: multi_no_shared_mutable
  read_consistency: strong
  idempotency: none
  time_source: server_clock
data_scope: all_data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    Over a fake sandbox gateway: opening a session on a succeeded run
    creates a sandbox from the examiner snapshot, copies konspekt.md and
    quiz.json, and stores the session active with the first examiner
    message of the open turn; opening on an unfinished run is 409 and
    stores nothing; a failed open turn is 503, stores nothing and
    deletes the sandbox; a turn whose sandbox is gone creates a new one
    and copies the materials before running; close sets closed and
    deletes the sandbox; a turn that masters the session deletes the
    sandbox.
  test_template: integration
  boundary_classes:
    - open on a succeeded run
    - open on an unfinished run
    - open turn failure
    - sandbox gone before a turn
    - close
    - session mastered
  failure_scenarios:
    - a session stored without its first question
    - a sandbox left running after mastered or closed
---
```

```yaml
---
id: service:REQ-004
type: Behavior
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.308Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: a student message is answered synchronously by one examiner turn
given: |
  - an active exam session (service:REQ-003)
when: a client posts a student message through POST /v1/exams/{exam_id}/messages (service:CON-003)
then: |
  the control plane claims the session's turn and runs one reply turn
  in the session's examiner sandbox (service:CON-004) with the session
  state, every earlier message in order and the new student message.
  Within the same request it stores the student message with its
  grading, the examiner message, the new state and the progress in one
  transaction and answers 200 with both messages. The examiner model
  receives the whole lecture notes, the current question with its
  answer key, its section title and video time range, and the question
  that follows for a correct and for a wrong answer. It classifies the
  student message as an answer to the current question, a question
  about the material or other; it explains a wrong answer from the
  lecture notes with the section title and video timestamp, answers a
  question about the material from the notes and repeats the current
  question, and is instructed never to state the answer of a question
  the student has not attempted. When the verdict the model states
  differs from the verdict computed from its graded fields
  (service:INV-001), the turn re-requests the reply once with the
  computed verdict. Every examiner message ends with the next question
  or, when every question is mastered, with a closing message.
negative_cases:
  - another turn of the session is claimed => 409
    EXAM_TURN_IN_PROGRESS; a claim older than 3 minutes counts as
    released
  - the session is mastered or closed => 409 EXAM_FINISHED
  - the turn fails, or the stated verdict still differs after the
    re-request => 503 EXAMINER_FAILED; nothing is stored and the claim
    is released
  - the turn runs longer than 120 s => 503 EXAMINER_TIMEOUT; nothing is
    stored and the claim is released
out_of_scope:
  - streaming the reply
  - editing or deleting messages
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: multi_no_shared_mutable
  read_consistency: strong
  idempotency: none
  time_source: server_clock
data_scope: all_data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    Over a fake sandbox gateway: a reply turn stores the student message
    with its grading, the examiner message and the progress atomically
    and returns both; a second message while a turn is claimed is 409
    EXAM_TURN_IN_PROGRESS; a claim older than 3 minutes does not block;
    a failed turn stores nothing and releases the claim; a turn over
    120 s is 503 EXAMINER_TIMEOUT; a message to a mastered session is
    409 EXAM_FINISHED.
    Over a fake examiner model: the turn prompt carries the current
    question's key, section title and time range and both follow-up
    questions; a stated verdict that differs from the computed one
    triggers exactly one re-request, and a second mismatch fails the
    turn.
  test_template: integration
  boundary_classes:
    - reply stored atomically
    - concurrent message
    - stale claim
    - turn failure and timeout
    - finished session
    - verdict mismatch re-request
  failure_scenarios:
    - a student message stored without the examiner reply
    - a session stuck with a claimed turn
---
```

```yaml
---
id: service:INV-001
type: Invariant
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.372Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: a quiz question is mastered only by an answer the examiner code grades correct
always: |
  In every exam session: questions are asked in quiz order. An answer
  to a single_choice or multi_select question in its original form is
  correct iff the set of options the examiner model extracted from the
  student message equals correct_options. An answer to an open question
  is correct iff the rubric points of the concepts the model marked
  covered sum to at least ceil(0.8 * max_points). A failed choice
  question is re-asked as an open question whose rubric has one 1-point
  concept per correct option, correct iff every such concept is
  covered; a failed open question is re-asked reworded with its own
  rubric. A correct answer marks the question mastered and removes it
  from the queue; a wrong answer marks it failed, counts the attempt
  and moves it to the end of the queue; a message that is not an answer
  changes no progress. The session is mastered iff every quiz question
  is mastered. Only these graded fields change progress; the model's
  reply text never does.
scope: konspekt/examiner-turn
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
  - a student message asking to be marked correct or to end the exam
    MUST NOT change progress unless its graded fields make it a correct
    answer
out_of_scope:
  - spaced repetition across sessions
  - questions beyond the run's quiz
test_obligation:
  predicate: |
    Policy unit tests: the exact option set is correct, a subset or a
    superset is wrong; an open answer at ceil(0.8 * max_points) is
    correct and one point below is wrong; a failed choice question comes
    back as open with one concept per correct option; a wrong answer
    moves the question to the end of the queue and counts the attempt;
    a non-answer changes nothing; the session is mastered only after
    the last question is mastered.
  test_template: unit
  boundary_classes:
    - choice exact, subset, superset
    - open threshold and one point below
    - failed choice re-asked as open
    - wrong answer requeued
    - non-answer
    - last question mastered
  failure_scenarios:
    - a question mastered by a reply that only claims correctness
    - a session mastered with a question left
---
```

## 7. Data contracts

```yaml
---
id: service:CON-001
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:06.025Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: client REST API
surface_ref: service:SUR-001
schema:
  base_url: "https://<deployment>.convex.site/v1"
  authentication: "header Authorization: Bearer <SERVICE_API_KEY>"
  endpoints:
    - "POST /v1/runs body {youtube_url: string, lang?: auto|ru|en (default
      auto), external_ref?: string <= 200 chars}; optional header
      Idempotency-Key; 202 {run_id, status: queued, video_id}"
    - "GET /v1/runs/{run_id} => 200 {run_id, external_ref, video_id,
      status: queued|provisioning|running|succeeded|failed, stages:
      [{name, completed_at}], error: {code, message} | null,
      llm_spend_usd: number | null, created_at, updated_at}"
    - "GET /v1/runs/{run_id}/result => 200 {run_id, video: {video_id,
      title, channel, duration_seconds}, outline, sections, claims, quiz,
      cut_log, files: [{kind: pdf|markdown|image, name, url, size_bytes,
      content_type}]}"
  result_shapes:
    - outline, sections, claims and cut_log use the shapes of the
      pipeline:CON-003 read tools get_outline, get_section, get_claims
      and get_cut_log
    - quiz uses the quiz export of output:CON-031
  run_error_codes:
    - SANDBOX_START_FAILED
    - WORKER_LOST
    - VIDEO_UNAVAILABLE
    - DOWNLOAD_FAILED
    - CONFIGURATION_ERROR
    - PIPELINE_FAILED
preconditions:
  - SERVICE_API_KEY is configured in the control-plane environment
postconditions:
  - a 202 response means the run is stored with status queued
  - the same Idempotency-Key returns the run created first
  - result is readable only for a succeeded run
external_identifiers:
  - paths /v1/runs, /v1/runs/{run_id}, /v1/runs/{run_id}/result
  - request fields youtube_url, lang, external_ref; header
    Idempotency-Key
  - response fields listed in schema; status values; run_error_codes
compatibility_rules:
  - removing or renaming a field, path, status or error code => major
    bump on service:SUR-001
  - adding an optional request field or a response field => minor bump
error_taxonomy:
  - "401 UNAUTHORIZED — missing or wrong API key"
  - "422 INPUT_NOT_YOUTUBE — host not youtube.com, www.youtube.com,
    m.youtube.com or youtu.be, or no video id (playlist or channel URL)"
  - "422 INVALID_REQUEST — malformed JSON or field types"
  - "404 RUN_NOT_FOUND"
  - "409 RUN_NOT_FINISHED — result requested before succeeded"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: multi_no_shared_mutable
  read_consistency: strong
  idempotency: "at_least_once_with_key:Idempotency-Key"
  time_source: server_clock
data_scope: all_data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    Control-plane tests: a valid watch, youtu.be, shorts and live URL is
    accepted with its video id; a playlist, channel or non-YouTube URL
    is rejected with INPUT_NOT_YOUTUBE; a wrong key is 401; a repeated
    Idempotency-Key returns the first run; status and result endpoints
    return 404 for an unknown run and 409 before success; a succeeded
    run returns its stored result with file URLs.
  test_template: contract
  boundary_classes:
    - accepted URL forms
    - rejected URL forms
    - wrong or missing key
    - idempotent resubmission
    - unknown run and unfinished run
    - succeeded run result
  failure_scenarios:
    - a run created for a non-YouTube URL
    - result served for an unfinished run
---
```

```yaml
---
id: service:CON-002
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:06.086Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: worker API
surface_ref: service:SUR-002
schema:
  base_url: "https://<deployment>.convex.site/worker"
  authentication: "header Authorization: Bearer <run token>; valid only
    for its own run and only while the run is provisioning or running"
  endpoints:
    - "POST /worker/runs/{run_id}/events body {type: stage_completed,
      stage: download|ingest|transcription|visual|segmentation|
      factcheck|notes|quiz|compose} or {type: heartbeat} => 204; the
      first event moves a provisioning run to running"
    - "POST /worker/runs/{run_id}/upload-url body {name, content_type,
      size_bytes <= 50 MB} => 200 {upload_url} (Convex storage upload
      URL); the worker POSTs the file there and receives a storage id"
    - "POST /worker/runs/{run_id}/complete body {status: succeeded,
      result: {video, outline, sections, claims, quiz, cut_log,
      llm_spend_usd}, files: [{kind, name, storage_id, size_bytes,
      content_type}]} or {status: failed, error: {code, message}} =>
      204"
preconditions:
  - the run exists and its token hash matches
postconditions:
  - a success completion stores every result document and the status
    succeeded in one transaction
  - after a terminal status every worker endpoint answers 409
external_identifiers:
  - paths under /worker/runs/{run_id}; event types; stage names; body
    fields listed in schema
compatibility_rules:
  - worker and snapshot are deployed together; any field change =>
    minor bump on service:SUR-002 with the snapshot rebuilt
error_taxonomy:
  - "401 — wrong token or token of another run"
  - "409 — run already terminal"
  - "413 — upload larger than 50 MB"
  - "422 — malformed body"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: server_clock
data_scope: all_data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    Control-plane tests: events with the right token record stages and
    move provisioning to running; another run's token is 401; an upload
    over 50 MB is 413; a success completion stores the result and the
    status atomically; any call after a terminal status is 409.
  test_template: contract
  boundary_classes:
    - valid event
    - foreign token
    - oversized upload
    - success completion
    - call after terminal status
  failure_scenarios:
    - partial result stored with status succeeded
---
```

```yaml
---
id: service:CON-003
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.059Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: exam client REST API
surface_ref: service:SUR-001
schema:
  base_url: "https://<deployment>.convex.site/v1"
  authentication: "header Authorization: Bearer <SERVICE_API_KEY>"
  endpoints:
    - "POST /v1/runs/{run_id}/exams (no body) => 201 {exam_id, run_id,
      status: active, progress, examiner_message: message}"
    - "GET /v1/exams/{exam_id} => 200 {exam_id, run_id, status:
      active|mastered|closed, progress, created_at, updated_at}"
    - "GET /v1/exams/{exam_id}/messages => 200 {messages: [message]} in
      seq order"
    - "POST /v1/exams/{exam_id}/messages body {text: string of 1 to 4000
      characters} => 200 {status, progress, student_message: message,
      examiner_message: message}"
    - "POST /v1/exams/{exam_id}/close (no body) => 200 {exam_id, status};
      an active session becomes closed, a mastered or closed session
      keeps its status"
  shapes:
    - "progress: {total, mastered, current_question_id: string | null,
      questions: [{question_id, section_title, status:
      pending|failed|mastered, attempts}]} with questions in quiz order;
      current_question_id is the question the examiner asked last, null
      once the session is mastered"
    - "message: {seq, role: examiner|student, text, question_id: string
      | null, verdict: correct|incorrect | null, created_at}; question_id
      and verdict are set on a student message graded as an answer"
preconditions:
  - SERVICE_API_KEY is configured in the control-plane environment
postconditions:
  - a 201 on open means the session and its first examiner message are
    stored
  - a 200 on a student message means both messages are stored
  - messages are returned in the order they were stored; seq starts at 1
    and grows by 1
external_identifiers:
  - paths /v1/runs/{run_id}/exams, /v1/exams/{exam_id},
    /v1/exams/{exam_id}/messages, /v1/exams/{exam_id}/close
  - request field text; response fields listed in schema; exam status
    values, question status values, roles, verdicts; error codes of the
    error taxonomy
compatibility_rules:
  - removing or renaming a field, path, status or error code => major
    bump on service:SUR-001
  - adding an optional request field or a response field => minor bump
error_taxonomy:
  - "401 UNAUTHORIZED — missing or wrong API key"
  - "404 RUN_NOT_FOUND — open on an unknown run"
  - "409 RUN_NOT_FINISHED — open on a run that is not succeeded"
  - "404 EXAM_NOT_FOUND"
  - "409 EXAM_FINISHED — student message to a mastered or closed session"
  - "409 EXAM_TURN_IN_PROGRESS — another student message of the session
    is being answered"
  - "422 INVALID_REQUEST — malformed JSON, text missing, empty or longer
    than 4000 characters"
  - "503 EXAMINER_FAILED — the examiner sandbox or model failed; nothing
    was stored"
  - "503 EXAMINER_TIMEOUT — the examiner did not answer within 120 s;
    nothing was stored"
  - "the edge in front of the deployment replaces 502 and 504 bodies, so
    examiner errors use 503 and are told apart by code"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: multi_no_shared_mutable
  read_consistency: strong
  idempotency: none
  time_source: server_clock
data_scope: all_data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    Control-plane tests over a fake sandbox gateway: a wrong key is 401
    on every exam path; open on an unknown run is 404 RUN_NOT_FOUND and
    on an unfinished run 409 RUN_NOT_FINISHED; open on a succeeded run
    is 201 with the first examiner message; an unknown exam is 404
    EXAM_NOT_FOUND; empty or 4001-character text is 422; a student
    message returns both messages with consecutive seq and the progress;
    messages are listed in seq order; close turns active into closed and
    keeps mastered; a message after close is 409 EXAM_FINISHED.
  test_template: contract
  boundary_classes:
    - authentication
    - open on unknown, unfinished and succeeded runs
    - text length bounds
    - message round trip and ordering
    - close semantics
  failure_scenarios:
    - an exam opened on a failed run
    - messages returned out of order
---
```

```yaml
---
id: service:CON-004
type: Contract
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.120Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: examiner turn protocol
surface_ref: service:SUR-003
schema:
  command: "konspekt-exam-turn <dir>"
  inputs:
    - "<dir>/konspekt.md — the run's lecture notes"
    - "<dir>/quiz.json — the run's quiz in the quiz export shape of
      output:CON-031"
    - "<dir>/turn.json — {kind: open} or {kind: reply, state, messages:
      [{role: examiner|student, text}], student_message: string}"
  output: "stdout, exit 0: one JSON object {state, progress,
    examiner_message: string, graded: {question_id, verdict:
    correct|incorrect} | null, is_mastered: boolean, llm_spend_usd:
    number}; progress has the shape of service:CON-003"
  state: "a JSON object produced by the previous turn; the control plane
    stores it verbatim and passes it back unchanged"
  failure: "non-zero exit; stderr carries the reason"
preconditions:
  - konspekt.md and quiz.json are the files of one succeeded run
  - a reply turn receives the state of the latest successful turn
postconditions:
  - an open turn makes no model call and returns every question pending
  - graded is null when the student message is not an answer
  - is_mastered is true iff every question in progress is mastered
external_identifiers:
  - command konspekt-exam-turn; file names konspekt.md, quiz.json,
    turn.json; turn kinds; output fields listed in schema
compatibility_rules:
  - the control plane and the examiner snapshot are deployed together;
    any field change => minor bump on service:SUR-003 with the snapshot
    rebuilt
error_taxonomy:
  - "exit 1 — the examiner model failed or stayed inconsistent after the
    re-request"
  - "exit 2 — missing or malformed input files"
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: none
data_scope: all_data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    Worker tests over a fake examiner model: an open turn returns the
    first question lettered A-D, every question pending and no model
    call; a reply turn returns the new state, progress and graded
    fields per service:INV-001; a non-answer returns graded null; the
    last mastered question sets is_mastered; a missing quiz.json exits
    2; a model failure exits 1.
  test_template: contract
  boundary_classes:
    - open turn
    - graded answer
    - non-answer
    - last question mastered
    - malformed input
    - model failure
  failure_scenarios:
    - a reply turn that drops earlier progress
---
```

## 8. Invariants

None beyond the postconditions of `service:CON-001` and `service:CON-002`.

## 9. External dependencies

```yaml
---
id: service:EXT-001
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:06.148Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
provider: Daytona sandboxes
provider_surface: "Daytona API via @daytona/sdk (snapshot create, sandbox create/delete, session commands)"
authority_url_or_doc: "https://www.daytona.io/docs/"
consumer_contract:
  request:
    - sandbox create from snapshot WORKER_SNAPSHOT with outboundProxyUrl
      PROXY_URL, envVars (worker variables and pipeline credentials),
      autoStopInterval 0, ttlMinutes 240, labels {run_id}
    - an asynchronous session command starts konspekt-worker
    - sandbox delete after a terminal run status
    - examiner sandbox create from snapshot EXAMINER_SNAPSHOT without an
      outbound proxy, envVars {CLAUDE_CODE_OAUTH_TOKEN}, ephemeral,
      autoStopInterval 15, labels {exam_id}
    - file upload of konspekt.md, quiz.json and turn.json into an
      examiner sandbox; a synchronous command runs konspekt-exam-turn
      with a 120 s timeout and returns its stdout and exit code
    - examiner sandbox delete after a mastered or closed session
  response_expectations:
    - sandbox id returned on create; the worker reaches the control
      plane directly or through the proxy
    - a get or command on a deleted examiner sandbox fails with a
      not-found error
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-09-12
auth_scope:
  - api key via control-plane env var DAYTONA_API_KEY
rate_limits:
  - "organization quota: resources of the tier; MAX_PARALLEL_RUNS keeps
    the service within it"
retry/idempotency:
  - create or start failure => the run fails with SANDBOX_START_FAILED;
    no retry
error_taxonomy:
  - "create, start or delete error => logged with run_id; delete errors
    do not change the run status"
sandbox_or_fixture:
  - control-plane tests use a fake sandbox gateway; no live Daytona
    calls in tests
test_obligation:
  predicate: |
    The gateway adapter sends the documented create parameters (snapshot,
    proxy, env, auto-stop 0, TTL 240, run label) and starts the worker
    command asynchronously; for an examiner sandbox it sends the
    examiner snapshot, no proxy, only CLAUDE_CODE_OAUTH_TOKEN, ephemeral
    and auto-stop 15, uploads files and runs the turn command with a
    120 s timeout; a failed create surfaces as a typed error and a
    missing sandbox as a distinct not-found error.
  test_template: contract
  boundary_classes:
    - create parameters
    - asynchronous worker start
    - create failure
    - examiner create parameters
    - synchronous turn command
    - missing examiner sandbox
  failure_scenarios:
    - secrets missing from the sandbox environment
---
```

```yaml
---
id: service:EXT-002
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:06.211Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
provider: YouTube through yt-dlp
provider_surface: "yt-dlp 2026.08.19 with yt-dlp-ejs and deno 2.9.6"
authority_url_or_doc: "https://github.com/yt-dlp/yt-dlp"
consumer_contract:
  request:
    - "yt-dlp --proxy $HTTPS_PROXY --ies youtube --no-playlist
      --ignore-config --no-remote-components -J <canonical watch URL>
      for metadata"
    - "yt-dlp ... -f 'bv*[height<=1080][vcodec^=vp9][protocol=https]+ba/
      bv*[height<=1080][protocol=https]+ba' --merge-output-format mkv"
  response_expectations:
    - metadata fields id, title, channel, duration, live_status,
      availability
drift_detection:
  mechanism: "none_with_review_by:2026-10-01"
last_verified_at: 2026-09-12
auth_scope:
  not_applicable: public_videos_only
  reason: only public videos are processed; no account cookies
rate_limits:
  - one download per run
retry/idempotency:
  - no retry inside a run
error_taxonomy:
  - "metadata failure or rejection => VIDEO_UNAVAILABLE"
  - "download or merge failure => DOWNLOAD_FAILED"
sandbox_or_fixture:
  - worker tests use a fake video source; no live YouTube in tests
test_obligation:
  predicate: |
    The worker's video source adapter builds the documented commands and
    maps a metadata JSON fixture to title, channel, duration and
    availability; a live, upcoming or private fixture is rejected.
  test_template: contract
  boundary_classes:
    - public metadata accepted
    - live or private rejected
    - command arguments
  failure_scenarios:
    - non-YouTube URL passed to yt-dlp
---
```

```yaml
---
id: service:EXT-003
type: ExternalDependency
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.436Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
provider: Claude Code CLI in the examiner sandbox
provider_surface: "claude-code-cli@>=2.1 (claude -p --output-format json --tools '' --system-prompt-file --json-schema)"
authority_url_or_doc: "https://code.claude.com/docs/en/cli-reference"
consumer_contract:
  invocations:
    - cmd: "claude -p --output-format json --model sonnet --tools ''
        --system-prompt-file <examiner protocol and lecture notes>
        --json-schema <turn schema>"
      stdin: the turn prompt (current question with its answer key, the
        follow-up questions, earlier messages, the student message)
      expects:
        - exit 0; stdout is one JSON object with structured_output
          matching the turn schema, is_error false and total_cost_usd
  authentication: CLAUDE_CODE_OAUTH_TOKEN in the examiner sandbox
    environment; ANTHROPIC_API_KEY is not set there
drift_detection:
  mechanism: "none_with_review_by:2026-11-01"
last_verified_at: 2026-09-12
auth_scope:
  - subscription token via CLAUDE_CODE_OAUTH_TOKEN (service:ASM-001)
rate_limits:
  - subscription plan limits; one invocation per turn, two when the
    verdict is re-requested
retry/idempotency:
  - structured_output missing or not matching the turn schema => one
    re-request, then the turn fails
error_taxonomy:
  - non-zero exit or is_error true => the turn fails with exit 1
sandbox_or_fixture:
  - tests use a fake runner; no live claude invocations in tests
test_obligation:
  predicate: |
    The examiner model adapter passes --tools '', the system prompt file
    and the turn schema, reads structured_output and total_cost_usd, and
    maps is_error, a non-zero exit and a schema mismatch after one
    re-request to a typed error; tested against a fake runner.
  test_template: contract
  boundary_classes:
    - invocation flags
    - structured output parsed
    - schema mismatch re-requested once
    - is_error mapped
  failure_scenarios:
    - the default Claude Code system prompt sent on every turn
---
```

## 10. Generated artifacts

```yaml
---
id: service:GEN-001
type: GeneratedArtifact
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:07:48.268Z
    change_request: OpenAPI description for the client team (user request in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: OpenAPI description of the client API for client teams
source_ids:
  - service:CON-001
  - service:CON-003
  - pipeline:CON-003
  - analysis:CON-021
  - analysis:CON-022
  - output:CON-031
generator: hand-authored rendering of the source contracts
command:
  not_applicable: hand_authored
  reason: no generator tool; the file changes in the same commit as any
    source contract it renders
output_paths:
  - control-plane/openapi.yaml
regeneration_mode: clean
published_surface: yes
surface_ref: service:SUR-001
applicability:
  invariant_to_all_axes: true
concurrency_model:
  actor_concurrency: single
  read_consistency: strong
  idempotency: none
  time_source: none
data_scope:
  not_applicable: static_document
  reason: the file describes the API and holds no persistent run data
policy_refs:
  - service:POL-001
test_obligation:
  predicate: |
    control-plane/openapi.yaml lists exactly the client operations the
    control plane routes (POST /v1/runs, GET /v1/runs/{run_id},
    GET /v1/runs/{run_id}/result, POST /v1/runs/{run_id}/exams,
    GET /v1/exams/{exam_id}, GET and POST /v1/exams/{exam_id}/messages,
    POST /v1/exams/{exam_id}/close); its enums for run statuses, stage
    names, languages, file kinds, run error codes, exam statuses,
    question statuses, message roles, verdicts and client error codes
    equal the control plane's vocabulary; real result and status
    responses validate against its schemas.
  test_template: contract
  boundary_classes:
    - operations match the router
    - enums match the vocabulary
    - run error codes cover worker and control-plane codes
  failure_scenarios:
    - a status, stage or error code added in code but missing from the
      published description
---
```

## 11. Localization

None: the API carries no user-facing text of its own.

## 12. Policies

```yaml
---
id: service:POL-001
type: Policy
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:06.277Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: callers are authenticated and secrets stay in the control plane
policy_kind: access_control
applicability:
  applies_to: every Behavior and Contract of partition service
predicate: |
  Every /v1 request carries the SERVICE_API_KEY; every /worker request
  carries the token of the run it addresses. Run tokens are stored only
  as sha256 hashes. DAYTONA_API_KEY, PROXY_URL, CLAUDE_CODE_OAUTH_TOKEN,
  ELEVENLABS_API_KEY, EXA_API_KEY and SERVICE_API_KEY live only in the
  control-plane environment and the run's sandbox environment, except
  that an examiner sandbox receives CLAUDE_CODE_OAUTH_TOKEN and no
  other secret; no endpoint response, run or exam document or log line
  contains them.
negative_test_obligations:
  - status and result responses of a run contain none of the configured
    secret values
  - exam responses contain none of the configured secret values
test_obligation:
  predicate: |
    Control-plane tests with sentinel secret values: no /v1 response and
    no stored run or exam document contains a sentinel; an examiner
    sandbox environment holds CLAUDE_CODE_OAUTH_TOKEN and no other
    sentinel; a worker call with a token of another run is rejected.
  test_template: integration
  boundary_classes:
    - sentinel secrets absent from responses and documents
    - foreign run token rejected
  failure_scenarios:
    - a secret echoed in an error message
---
```

## 13. Constraints

```yaml
---
id: service:CST-001
type: Constraint
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:06.346Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
title: the control plane runs on its own Convex deployment
constraint: |
  The control plane is a Convex project in control-plane/ deployed to a
  deployment separate from the client's; its HTTP API is served by
  Convex HTTP actions, run results are Convex documents and files live
  in Convex file storage.
rationale: |
  The client team already uses Convex; a separate deployment keeps the
  service's secrets, billing and data apart from the client while
  reusing the same platform.
test_obligation:
  not_applicable: deployment_topology_only
  reason: the constraint fixes where the control plane runs; its
    behavior is tested through service:CON-001 and service:CON-002
---
```

## 14. Migrations

None.

## 15. Deltas

```yaml
---
id: service:DLT-001
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:08:14.686Z
    change_request: OpenAPI description for the client team (user request in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
target_id: service:SUR-001
kind: extend
compatibility_action: ignore
baseline_version: db9f042
summary: |
  service:SUR-001 gains the published OpenAPI description
  (service:GEN-001, control-plane/openapi.yaml) as a member so client
  teams can generate types and read the full result schema; the API
  itself is unchanged => 0.2.0 (additive).
tests_old_behavior:
  - control-plane/convex/clientApi.test.ts (client API unchanged)
tests_new_behavior:
  - control-plane/convex/openapiDescription.test.ts (description matches
    the control plane)
---
```

```yaml
---
id: service:DLT-002
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.562Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
target_id: service:SUR-001
kind: extend
compatibility_action: ignore
baseline_version: 0247071
summary: |
  service:SUR-001 gains the exam client API (service:CON-003): open an
  exam session on a succeeded run, exchange messages with the examiner
  synchronously, read progress and history, close the session. Existing
  run endpoints are unchanged.
tests_old_behavior:
  - control-plane/convex/clientApi.test.ts (run endpoints unchanged)
tests_new_behavior:
  - control-plane/convex/examApi.test.ts (exam endpoints)
---
```

```yaml
---
id: service:DLT-003
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.626Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
target_id: service:POL-001
kind: extend
compatibility_action: ignore
baseline_version: 0247071
summary: |
  Examiner sandboxes receive CLAUDE_CODE_OAUTH_TOKEN and no other
  secret; exam responses and exam documents join the places that never
  contain a secret.
tests_old_behavior:
  - control-plane/convex/secretPolicy.test.ts (run responses)
tests_new_behavior:
  - control-plane/convex/secretPolicy.test.ts (exam responses and
    examiner sandbox environment)
---
```

```yaml
---
id: service:DLT-004
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.692Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
target_id: service:EXT-001
kind: extend
compatibility_action: ignore
baseline_version: 0247071
summary: |
  The control plane also creates ephemeral examiner sandboxes from
  EXAMINER_SNAPSHOT without the outbound proxy, auto-stopping after 15
  idle minutes, uploads files into them and runs konspekt-exam-turn
  synchronously with a 120 s timeout.
tests_old_behavior:
  - control-plane/convex/sandbox/daytonaSandboxGateway.test.ts (run
    sandbox parameters)
tests_new_behavior:
  - control-plane/convex/sandbox/daytonaSandboxGateway.test.ts
    (examiner sandbox parameters, upload, synchronous turn command)
---
```

```yaml
---
id: service:DLT-005
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.755Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
target_id: service:GEN-001
kind: extend
compatibility_action: ignore
baseline_version: 0247071
summary: |
  The OpenAPI description also renders the exam client API
  (service:CON-003).
tests_old_behavior:
  - control-plane/convex/openapiDescription.test.ts (run operations)
tests_new_behavior:
  - control-plane/convex/openapiDescription.test.ts (exam operations,
    exam statuses and exam error codes)
---
```

```yaml
---
id: service:DLT-006
type: Delta
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T15:17:41.954Z
    change_request: examiner errors on 503 behind the Convex edge (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
target_id: service:CON-003
kind: replace
compatibility_action: ignore
baseline_version: 0247071
summary: |
  EXAMINER_FAILED and EXAMINER_TIMEOUT answer 503 instead of 502 and
  504 (service:CON-003, service:REQ-003, service:REQ-004): the edge in
  front of the Convex deployment replaces 502 and 504 response bodies
  with its own page, so the client would lose the JSON error code. The
  two causes stay distinct through the code field. No client used the
  previous statuses.
tests_old_behavior:
  - control-plane/convex/examApi.test.ts (examiner failures stored
    nothing)
tests_new_behavior:
  - control-plane/convex/examApi.test.ts (examiner failures answer 503
    with EXAMINER_FAILED or EXAMINER_TIMEOUT)
---
```

## 16. Implementation bindings

None.

## 17. Open questions

None.

## 18. Assumptions

```yaml
---
id: service:ASM-001
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T12:47:06.408Z
    change_request: konspekt cloud service partition (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
assumption: |
  Pitch-demo scope: the worker authenticates Claude Code with the
  owner's subscription token (CLAUDE_CODE_OAUTH_TOKEN); production moves
  to API billing. Results are kept without a retention limit. Clients
  submit only videos they have the rights to process.
blocking: no
review_by: 2026-10-15
default_if_unresolved: keep_assumption
tests:
  - not_applicable: process_assumption_no_runtime_behavior
---
```

```yaml
---
id: service:ASM-002
type: ASSUMPTION
lifecycle:
  status: approved
  approval_record:
    owner_role: tech-lead
    approver_identity: cyberash
    timestamp: 2026-09-12T14:49:08.500Z
    change_request: exam sessions with the examiner (user approval in chat 2026-09-12, approval delegated per pipeline:ASM-001)
    scope: first-time-approval
partition_id: service
assumption: |
  Pitch-demo scope for exam sessions: the service stores no student
  identity and the client maps exam ids to its users; exam messages are
  kept without a retention limit like run results; the Daytona
  organization quota holds the concurrent examiner sandboxes (1 vCPU,
  2 GiB each) next to the run sandbox, so concurrent exam sessions are
  not capped.
blocking: no
review_by: 2026-10-15
default_if_unresolved: keep_assumption
tests:
  - not_applicable: process_assumption_no_runtime_behavior
---
```

## 19. Out of scope

- retrying or cancelling a run; a client submits a new run instead
- user accounts, quotas and billing: owned by the client
- non-YouTube sources and file uploads
- resuming a failed run in a new sandbox
