import { describe, expect, it, vi } from "vitest";
import { CLOCK_START, runScheduledFunctions, SENTINEL_SECRETS } from "../test-support/controlPlane";
import {
  CLOSING_MESSAGE,
  EXAMINER_SNAPSHOT,
  examControlPlane,
  examProgress,
  fakeExaminerInUse,
  firstAnswerCorrectOutput,
  LECTURE_NOTES,
  lastAnswerCorrectOutput,
  OPEN_MESSAGE,
  openTurnOutput,
  SECOND_QUESTION_MESSAGE,
  succeededRunId,
} from "../test-support/examArrangement";
import {
  getExam,
  openedExamId,
  postCloseExam,
  postOpenExam,
  postStudentMessage,
} from "../test-support/examCalls";
import { jsonObjectOf, submittedRunId } from "../test-support/httpCalls";
import { lectureResult } from "../test-support/runArrangement";
import { internal } from "./_generated/api";

vi.mock("./sandbox/examinerGatewayFactory", () => ({ daytonaExaminerGateway: vi.fn() }));

const WATCH_URL = "https://www.youtube.com/watch?v=ZA-tUyM_y7s";
const MINUTE_MS = 60 * 1000;
const CLOCK_START_ISO = CLOCK_START.toISOString();

/* @covers service:DLT-002 */
describe("POST /v1/runs/{run_id}/exams", () => {
  /* @covers service:CON-003 */
  /* @covers service:REQ-003 */
  it("opens an active session on a succeeded run with the first examiner message", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() });
    const runId = await succeededRunId(controlPlane);

    const response = await postOpenExam(controlPlane, runId);

    expect(response.status).toBe(201);
    expect(await jsonObjectOf(response)).toEqual({
      exam_id: expect.any(String),
      run_id: runId,
      status: "active",
      progress: examProgress(["pending", "pending"], "q1"),
      examiner_message: {
        seq: 1,
        role: "examiner",
        text: OPEN_MESSAGE,
        question_id: null,
        verdict: null,
        created_at: CLOCK_START_ISO,
      },
    });
  });

  /* @covers service:REQ-003 */
  /* @covers service:EXT-001 */
  it("creates the examiner sandbox from EXAMINER_SNAPSHOT with the Claude token and the exam label", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    expect(gateway.createdSpecs).toEqual([
      {
        snapshot: EXAMINER_SNAPSHOT,
        labels: { exam_id: examId },
        envVars: {
          CLAUDE_CODE_OAUTH_TOKEN: SENTINEL_SECRETS.CLAUDE_CODE_OAUTH_TOKEN,
          CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1",
        },
      },
    ]);
  });

  /* @covers service:REQ-003 */
  it("copies konspekt.md and quiz.json into the sandbox before the open turn", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers({ kind: "output", output: openTurnOutput() });

    await openedExamId(controlPlane, await succeededRunId(controlPlane));

    expect(gateway.uploads).toEqual([
      { sandboxId: "examiner-sandbox-1", name: "konspekt.md", text: LECTURE_NOTES },
      { sandboxId: "examiner-sandbox-1", name: "quiz.json", text: JSON.stringify(lectureResult().quiz) },
      { sandboxId: "examiner-sandbox-1", name: "turn.json", text: JSON.stringify({ kind: "open" }) },
    ]);
    expect(gateway.turnSandboxIds).toEqual(["examiner-sandbox-1"]);
  });

  /* @covers service:CON-003 */
  it("answers 404 RUN_NOT_FOUND for an unknown run", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse();

    const response = await postOpenExam(controlPlane, "unknown-run");

    expect(response.status).toBe(404);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "RUN_NOT_FOUND" } });
  });

  /* @covers service:CON-003 */
  /* @covers service:REQ-003 */
  it("answers 409 RUN_NOT_FINISHED for a run that has not succeeded", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse();
    const runId = await submittedRunId(controlPlane, WATCH_URL);

    const response = await postOpenExam(controlPlane, runId);

    expect(response.status).toBe(409);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "RUN_NOT_FINISHED" } });
  });

  /* @covers service:REQ-003 */
  it("starts no sandbox and stores no session for a run that has not succeeded", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    const runId = await submittedRunId(controlPlane, WATCH_URL);

    await postOpenExam(controlPlane, runId);

    expect(gateway.createdSpecs).toEqual([]);
    expect(await controlPlane.run(async (ctx) => ctx.db.query("exams").collect())).toEqual([]);
  });

  /* @covers service:REQ-003 */
  /* @covers service:CON-003 */
  it.each([
    ["a non-zero exit", { kind: "exit", exitCode: 1, stderr: "model failed" }],
    ["stdout that is not JSON", { kind: "stdout", stdout: "Traceback (most recent call last)" }],
    ["output without progress", { kind: "output", output: { ...openTurnOutput(), progress: null } }],
    ["a verdict outside the protocol", { kind: "output", output: { ...openTurnOutput(), graded: { question_id: "q1", verdict: "maybe" } } }],
    ["a run longer than 120 s", { kind: "timeout" }],
  ] as const)("answers 503 EXAMINER_FAILED when the open turn ends with %s", async (_case, turn) => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(turn);
    const runId = await succeededRunId(controlPlane);

    const response = await postOpenExam(controlPlane, runId);

    expect(response.status).toBe(503);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "EXAMINER_FAILED" } });
  });

  /* @covers service:REQ-003 */
  it.each([
    ["fails", { kind: "exit", exitCode: 1, stderr: "model failed" }],
    ["times out", { kind: "timeout" }],
  ] as const)("stores no session and no message when the open turn %s", async (_case, turn) => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(turn);
    const runId = await succeededRunId(controlPlane);

    await postOpenExam(controlPlane, runId);

    const documents = await controlPlane.run(async (ctx) => [
      ...(await ctx.db.query("exams").collect()),
      ...(await ctx.db.query("exam_messages").collect()),
    ]);
    expect(documents).toEqual([]);
  });

  /* @covers service:REQ-003 */
  it.each([
    ["fails", { kind: "exit", exitCode: 2, stderr: "quiz.json missing" }],
    ["times out", { kind: "timeout" }],
  ] as const)("deletes the sandbox when the open turn %s", async (_case, turn) => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers(turn);
    const runId = await succeededRunId(controlPlane);

    await postOpenExam(controlPlane, runId);

    expect(gateway.deletedSandboxIds).toEqual(["examiner-sandbox-1"]);
  });

  /* @covers service:REQ-003 */
  it("answers 503 EXAMINER_FAILED and stores nothing when the sandbox cannot be created", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse("organization quota exceeded");
    const runId = await succeededRunId(controlPlane);

    const response = await postOpenExam(controlPlane, runId);

    expect(response.status).toBe(503);
    expect(await controlPlane.run(async (ctx) => ctx.db.query("exams").collect())).toEqual([]);
  });
});

/* @covers service:DLT-002 */
describe("exam authentication", () => {
  /* @covers service:CON-003 */
  it.each([
    ["POST", "/v1/runs/run-1/exams"],
    ["GET", "/v1/exams/exam-1"],
    ["GET", "/v1/exams/exam-1/messages"],
    ["POST", "/v1/exams/exam-1/messages"],
    ["POST", "/v1/exams/exam-1/close"],
  ])("answers 401 UNAUTHORIZED to %s %s with a wrong API key", async (method, path) => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse();

    const response = await controlPlane.fetch(path, {
      method,
      headers: { Authorization: "Bearer not-the-service-key" },
    });

    expect(response.status).toBe(401);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "UNAUTHORIZED" } });
  });
});

/* @covers service:DLT-002 */
describe("GET /v1/exams/{exam_id}", () => {
  /* @covers service:CON-003 */
  it("returns the stored session", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() });
    const runId = await succeededRunId(controlPlane);
    const examId = await openedExamId(controlPlane, runId);

    const response = await getExam(controlPlane, examId);

    expect(response.status).toBe(200);
    expect(await jsonObjectOf(response)).toEqual({
      exam_id: examId,
      run_id: runId,
      status: "active",
      progress: examProgress(["pending", "pending"], "q1"),
      created_at: CLOCK_START_ISO,
      updated_at: CLOCK_START_ISO,
    });
  });

  /* @covers service:CON-003 */
  it.each([
    ["GET", "/v1/exams/unknown-exam", null],
    ["GET", "/v1/exams/unknown-exam/messages", null],
    ["POST", "/v1/exams/unknown-exam/messages", JSON.stringify({ text: "B" })],
    ["POST", "/v1/exams/unknown-exam/close", null],
  ])("answers 404 EXAM_NOT_FOUND to %s %s", async (method, path, body) => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse();

    const response = await controlPlane.fetch(path, {
      method,
      headers: { Authorization: `Bearer ${SENTINEL_SECRETS.SERVICE_API_KEY}` },
      body,
    });

    expect(response.status).toBe(404);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "EXAM_NOT_FOUND" } });
  });
});

/* @covers service:DLT-002 */
describe("POST /v1/exams/{exam_id}/messages", () => {
  /* @covers service:CON-003 */
  /* @covers service:REQ-004 */
  it("answers a student message with both messages, consecutive seq and the progress", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    vi.setSystemTime(CLOCK_START.getTime() + MINUTE_MS);

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(response.status).toBe(200);
    expect(await jsonObjectOf(response)).toEqual({
      status: "active",
      progress: examProgress(["mastered", "pending"], "q2"),
      student_message: {
        seq: 2,
        role: "student",
        text: "B",
        question_id: "q1",
        verdict: "correct",
        created_at: new Date(CLOCK_START.getTime() + MINUTE_MS).toISOString(),
      },
      examiner_message: {
        seq: 3,
        role: "examiner",
        text: SECOND_QUESTION_MESSAGE,
        question_id: null,
        verdict: null,
        created_at: new Date(CLOCK_START.getTime() + MINUTE_MS).toISOString(),
      },
    });
  });

  /* @covers service:CON-003 */
  /* @covers service:REQ-004 */
  it("lists the stored messages in seq order with the student's grading", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postStudentMessage(controlPlane, examId, { text: "B" });

    const response = await getExam(controlPlane, `${examId}/messages`);

    expect(response.status).toBe(200);
    expect(await jsonObjectOf(response)).toEqual({
      messages: [
        { seq: 1, role: "examiner", text: OPEN_MESSAGE, question_id: null, verdict: null, created_at: CLOCK_START_ISO },
        { seq: 2, role: "student", text: "B", question_id: "q1", verdict: "correct", created_at: CLOCK_START_ISO },
        { seq: 3, role: "examiner", text: SECOND_QUESTION_MESSAGE, question_id: null, verdict: null, created_at: CLOCK_START_ISO },
      ],
    });
  });

  /* @covers service:REQ-004 */
  it("runs a reply turn with the latest state, every earlier message in order and the new message", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
      { kind: "output", output: lastAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postStudentMessage(controlPlane, examId, { text: "B" });

    await postStudentMessage(controlPlane, examId, { text: "A" });

    expect(gateway.turnInputs()[2]).toEqual({
      kind: "reply",
      state: firstAnswerCorrectOutput().state,
      messages: [
        { role: "examiner", text: OPEN_MESSAGE },
        { role: "student", text: "B" },
        { role: "examiner", text: SECOND_QUESTION_MESSAGE },
      ],
      student_message: "A",
    });
  });

  /* @covers service:CON-003 */
  it.each([
    ["an empty", { text: "" }],
    ["a 4001-character", { text: "x".repeat(4001) }],
    ["a missing", {}],
    ["a numeric", { text: 42 }],
  ])("rejects %s text with INVALID_REQUEST", async (_case, body) => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    const response = await postStudentMessage(controlPlane, examId, body);

    expect(response.status).toBe(422);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "INVALID_REQUEST" } });
  });

  /* @covers service:CON-003 */
  it("accepts a text of exactly 4000 characters", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    const response = await postStudentMessage(controlPlane, examId, { text: "x".repeat(4000) });

    expect(response.status).toBe(200);
  });

  /* @covers service:CON-003 */
  it("rejects malformed JSON with INVALID_REQUEST", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    const response = await controlPlane.fetch(`/v1/exams/${examId}/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${SENTINEL_SECRETS.SERVICE_API_KEY}` },
      body: "{\"text\":",
    });

    expect(response.status).toBe(422);
    expect(await jsonObjectOf(response)).toEqual({
      error: { code: "INVALID_REQUEST", message: "body is not valid JSON" },
    });
  });

  /* @covers service:REQ-004 */
  it("answers 409 EXAM_TURN_IN_PROGRESS while another turn of the session is claimed", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await controlPlane.mutation(internal.examTurns.claimTurn, { examId });
    vi.setSystemTime(CLOCK_START.getTime() + 3 * MINUTE_MS);

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(response.status).toBe(409);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "EXAM_TURN_IN_PROGRESS" } });
  });

  /* @covers service:REQ-004 */
  it("answers a message when the other claim is older than 3 minutes", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await controlPlane.mutation(internal.examTurns.claimTurn, { examId });
    vi.setSystemTime(CLOCK_START.getTime() + 3 * MINUTE_MS + 1);

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(response.status).toBe(200);
  });

  /* @covers service:REQ-004 */
  /* @covers service:CON-003 */
  /* @covers service:DLT-006 */
  it("answers 503 EXAMINER_FAILED when the reply turn fails", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "exit", exitCode: 1, stderr: "verdict still inconsistent after the re-request" },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(response.status).toBe(503);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "EXAMINER_FAILED" } });
  });

  /* @covers service:REQ-004 */
  it.each([
    ["fails", { kind: "exit", exitCode: 1, stderr: "model failed" }],
    ["times out", { kind: "timeout" }],
  ] as const)("keeps the messages and progress when the reply turn %s", async (_case, turn) => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() }, turn);
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    await postStudentMessage(controlPlane, examId, { text: "B" });

    const stored = await Promise.all([
      jsonObjectOf(await getExam(controlPlane, examId)),
      jsonObjectOf(await getExam(controlPlane, `${examId}/messages`)),
    ]);
    expect(stored).toEqual([
      expect.objectContaining({ progress: examProgress(["pending", "pending"], "q1") }),
      { messages: [expect.objectContaining({ seq: 1, role: "examiner" })] },
    ]);
  });

  /* @covers service:REQ-004 */
  it.each([
    ["fails", { kind: "exit", exitCode: 1, stderr: "model failed" }],
    ["times out", { kind: "timeout" }],
  ] as const)("releases the claim when the reply turn %s", async (_case, turn) => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      turn,
      { kind: "output", output: firstAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postStudentMessage(controlPlane, examId, { text: "B" });

    const retry = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(retry.status).toBe(200);
  });

  /* @covers service:REQ-004 */
  /* @covers service:CON-003 */
  /* @covers service:DLT-006 */
  it("answers 503 EXAMINER_TIMEOUT when the reply turn runs longer than 120 s", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() }, { kind: "timeout" });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(response.status).toBe(503);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "EXAMINER_TIMEOUT" } });
  });

  /* @covers service:REQ-003 */
  /* @covers service:CON-003 */
  it("reports the session mastered when the turn masters every question", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: lastAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(await jsonObjectOf(response)).toMatchObject({
      status: "mastered",
      progress: examProgress(["mastered", "mastered"], null),
      examiner_message: { text: CLOSING_MESSAGE },
    });
  });

  /* @covers service:REQ-004 */
  it("answers 409 EXAM_FINISHED to a message for a mastered session", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: lastAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postStudentMessage(controlPlane, examId, { text: "B" });

    const response = await postStudentMessage(controlPlane, examId, { text: "one more" });

    expect(response.status).toBe(409);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "EXAM_FINISHED" } });
  });

  /* @covers service:CON-003 */
  it("answers 409 EXAM_FINISHED to a message after close", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postCloseExam(controlPlane, examId);

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(response.status).toBe(409);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "EXAM_FINISHED" } });
  });
});

/* @covers service:DLT-002 */
describe("POST /v1/exams/{exam_id}/close", () => {
  /* @covers service:CON-003 */
  /* @covers service:REQ-003 */
  it("closes an active session", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));

    const response = await postCloseExam(controlPlane, examId);

    expect(response.status).toBe(200);
    expect(await jsonObjectOf(response)).toEqual({ exam_id: examId, status: "closed" });
  });

  /* @covers service:CON-003 */
  it("keeps a mastered session mastered", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: lastAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postStudentMessage(controlPlane, examId, { text: "B" });

    const response = await postCloseExam(controlPlane, examId);

    expect(response.status).toBe(200);
    expect(await jsonObjectOf(response)).toEqual({ exam_id: examId, status: "mastered" });
  });
});

/* @covers service:DLT-002 */
describe("examiner sandbox lifecycle", () => {
  /* @covers service:REQ-003 */
  it("deletes the sandbox of a closed session", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postCloseExam(controlPlane, examId);

    await runScheduledFunctions(controlPlane);

    expect(gateway.deletedSandboxIds).toEqual(["examiner-sandbox-1"]);
  });

  /* @covers service:REQ-003 */
  it("deletes the sandbox when a turn masters the session", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: lastAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postStudentMessage(controlPlane, examId, { text: "B" });

    await runScheduledFunctions(controlPlane);

    expect(gateway.deletedSandboxIds).toEqual(["examiner-sandbox-1"]);
  });

  /* @covers service:REQ-003 */
  it("creates a new sandbox and copies the materials before a turn whose sandbox is gone", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    gateway.lose("examiner-sandbox-1");

    const response = await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(response.status).toBe(200);
    expect(gateway.uploadedNames("examiner-sandbox-2")).toEqual(["konspekt.md", "quiz.json", "turn.json"]);
    expect(gateway.turnSandboxIds).toEqual(["examiner-sandbox-1", "examiner-sandbox-2"]);
  });

  /* @covers service:REQ-003 */
  it("runs later turns in the replacement sandbox", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
      { kind: "output", output: lastAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    gateway.lose("examiner-sandbox-1");
    await postStudentMessage(controlPlane, examId, { text: "B" });

    await postStudentMessage(controlPlane, examId, { text: "A" });

    expect(gateway.turnSandboxIds).toEqual(["examiner-sandbox-1", "examiner-sandbox-2", "examiner-sandbox-2"]);
  });

  /* @covers service:REQ-003 */
  it("deletes a replacement sandbox recorded after the session was closed", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers({ kind: "output", output: openTurnOutput() });
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postCloseExam(controlPlane, examId);

    await controlPlane.mutation(internal.examTurns.recordSandbox, { examId, sandboxId: "examiner-sandbox-late" });
    await runScheduledFunctions(controlPlane);

    expect(gateway.deletedSandboxIds).toEqual(["examiner-sandbox-1", "examiner-sandbox-late"]);
  });
});
