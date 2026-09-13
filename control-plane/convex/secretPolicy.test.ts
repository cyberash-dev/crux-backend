import { describe, expect, it, vi } from "vitest";
import {
  controlPlaneWithFakeClock,
  runScheduledFunctions,
  SENTINEL_SECRETS,
  sentinelSecretsIn,
} from "../test-support/controlPlane";
import {
  examControlPlane,
  fakeExaminerInUse,
  firstAnswerCorrectOutput,
  openTurnOutput,
  succeededRunId,
} from "../test-support/examArrangement";
import {
  getExam,
  openedExamId,
  postCloseExam,
  postOpenExam,
  postStudentMessage,
} from "../test-support/examCalls";
import { fakeGatewayInUse } from "../test-support/fakeGatewayInUse";
import { getRun, jsonObjectOf, postWorker, submittedRunId } from "../test-support/httpCalls";
import { storedFileId, succeededCompletion } from "../test-support/runArrangement";

vi.mock("./sandbox/daytonaGatewayFactory", () => ({ daytonaSandboxGateway: vi.fn() }));
vi.mock("./sandbox/examinerGatewayFactory", () => ({ daytonaExaminerGateway: vi.fn() }));

const WATCH_URL = "https://www.youtube.com/watch?v=ZA-tUyM_y7s";
const SECRET_ECHO = `proxy ${SENTINEL_SECRETS.PROXY_URL} rejected key ${SENTINEL_SECRETS.DAYTONA_API_KEY}`;
const LISTED_PROXY_A = "http://listed-user-a:listed-pass-a@proxy-a.test:3128";
const LISTED_PROXY_B = "http://listed-user-b:listed-pass-b@proxy-b.test:3128";

describe("secrets stay in the control plane", () => {
  /* @covers service:POL-001 */
  it("serves a sandbox error that echoes secrets with the secrets redacted", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    fakeGatewayInUse({ operation: "create", message: SECRET_ECHO });
    const runId = await submittedRunId(controlPlane, WATCH_URL);
    await runScheduledFunctions(controlPlane);

    const response = await getRun(controlPlane, runId);

    expect((await jsonObjectOf(response)).error).toEqual({
      code: "SANDBOX_START_FAILED",
      message: "sandbox create failed: proxy [redacted] rejected key [redacted]",
    });
  });

  /* @covers service:POL-001 */
  it("logs a sandbox start failure with the echoed secrets redacted", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => undefined);
    fakeGatewayInUse({ operation: "create", message: SECRET_ECHO });
    const runId = await submittedRunId(controlPlane, WATCH_URL);

    await runScheduledFunctions(controlPlane);

    expect(errorLog.mock.calls).toEqual([
      [
        "sandbox.start_failed",
        { run_id: runId, message: "sandbox create failed: proxy [redacted] rejected key [redacted]" },
      ],
    ]);
  });

  /* @covers service:POL-001 */
  it("serves a worker failure message that echoes a secret with the secret redacted", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, WATCH_URL);
    await runScheduledFunctions(controlPlane);
    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), {
      status: "failed",
      error: { code: "CONFIGURATION_ERROR", message: `bad token ${SENTINEL_SECRETS.CLAUDE_CODE_OAUTH_TOKEN}` },
    });

    const response = await getRun(controlPlane, runId);

    expect((await jsonObjectOf(response)).error).toEqual({
      code: "CONFIGURATION_ERROR",
      message: "bad token [redacted]",
    });
  });

  /* @covers service:POL-001 */
  /* @covers service:DLT-009 */
  it("serves a worker failure message that echoes each PROXY_URL entry with every entry redacted", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", `${LISTED_PROXY_A}, ${LISTED_PROXY_B}`);
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, WATCH_URL);
    await runScheduledFunctions(controlPlane);
    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), {
      status: "failed",
      error: { code: "DOWNLOAD_FAILED", message: `via ${LISTED_PROXY_B} after ${LISTED_PROXY_A}` },
    });

    const response = await getRun(controlPlane, runId);

    expect((await jsonObjectOf(response)).error).toEqual({
      code: "DOWNLOAD_FAILED",
      message: "via [redacted] after [redacted]",
    });
  });

  /* @covers service:POL-001 */
  /* @covers service:DLT-009 */
  it("stores no PROXY_URL entry in any document after a blocked run is provisioned again", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", `${LISTED_PROXY_A},${LISTED_PROXY_B}`);
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, WATCH_URL);
    await runScheduledFunctions(controlPlane);
    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), {
      status: "failed",
      error: { code: "DOWNLOAD_BLOCKED", message: `blocked via ${LISTED_PROXY_A}` },
    });
    await runScheduledFunctions(controlPlane);

    const documentsText = JSON.stringify(
      await controlPlane.run(async (ctx) => [
        ...(await ctx.db.query("runs").collect()),
        ...(await ctx.db.query("proxy_rotation").collect()),
      ]),
    );

    expect([LISTED_PROXY_A, LISTED_PROXY_B].filter((proxyUrl) => documentsText.includes(proxyUrl))).toEqual([]);
  });

  /* @covers service:POL-001 */
  it("serves the status and result of a succeeded run without secrets", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, WATCH_URL);
    await runScheduledFunctions(controlPlane);
    const pdfId = await storedFileId(controlPlane, "%PDF-1.7");
    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), succeededCompletion([
      { kind: "pdf", name: "konspekt.pdf", storage_id: pdfId, size_bytes: 8, content_type: "application/pdf" },
    ]));

    const responseTexts = await Promise.all([
      (await getRun(controlPlane, runId)).text(),
      (await getRun(controlPlane, `${runId}/result`)).text(),
    ]);

    expect(sentinelSecretsIn(responseTexts.join("\n"))).toEqual([]);
  });

  /* @covers service:POL-001 */
  it("stores no secret in any run document after failed and succeeded runs", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("MAX_PARALLEL_RUNS", "2");
    const gateway = fakeGatewayInUse();
    const failedRunId = await submittedRunId(controlPlane, WATCH_URL);
    const succeededRunId = await submittedRunId(controlPlane, "https://youtu.be/9bZkp7q19f0");
    await runScheduledFunctions(controlPlane);
    await postWorker(controlPlane, { runId: failedRunId, endpoint: "complete" }, gateway.runToken(failedRunId), {
      status: "failed",
      error: { code: "PIPELINE_FAILED", message: `exa rejected ${SENTINEL_SECRETS.EXA_API_KEY}` },
    });
    await postWorker(
      controlPlane,
      { runId: succeededRunId, endpoint: "complete" },
      gateway.runToken(succeededRunId),
      succeededCompletion([]),
    );

    const documents = await controlPlane.run(async (ctx) => [
      ...(await ctx.db.query("runs").collect()),
      ...(await ctx.db.query("run_results").collect()),
      ...(await ctx.db.query("run_sections").collect()),
      ...(await ctx.db.query("run_files").collect()),
    ]);

    expect(sentinelSecretsIn(JSON.stringify(documents))).toEqual([]);
  });
});

/* @covers service:DLT-003 */
describe("exam secrets stay in the control plane", () => {
  /* @covers service:POL-001 */
  it("serves every exam response without secrets, including a failed turn that echoes them", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
      { kind: "exit", exitCode: 1, stderr: SECRET_ECHO },
    );
    const opened = await postOpenExam(controlPlane, await succeededRunId(controlPlane));
    const examId = String((await jsonObjectOf(opened.clone())).exam_id);

    const responses = [
      opened,
      await postStudentMessage(controlPlane, examId, { text: "B" }),
      await postStudentMessage(controlPlane, examId, { text: "A" }),
      await getExam(controlPlane, examId),
      await getExam(controlPlane, `${examId}/messages`),
      await postCloseExam(controlPlane, examId),
    ];

    const responseTexts = await Promise.all(responses.map(async (response) => response.text()));
    expect(sentinelSecretsIn(responseTexts.join("\n"))).toEqual([]);
  });

  /* @covers service:POL-001 */
  it("stores no secret in any exam document", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "output", output: firstAnswerCorrectOutput() },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    await postStudentMessage(controlPlane, examId, { text: "B" });

    const documents = await controlPlane.run(async (ctx) => [
      ...(await ctx.db.query("exams").collect()),
      ...(await ctx.db.query("exam_messages").collect()),
    ]);

    expect(sentinelSecretsIn(JSON.stringify(documents))).toEqual([]);
  });

  /* @covers service:POL-001 */
  it("gives the examiner sandbox CLAUDE_CODE_OAUTH_TOKEN and no other secret", async () => {
    const controlPlane = examControlPlane();
    const gateway = fakeExaminerInUse();
    gateway.answers({ kind: "output", output: openTurnOutput() });

    await openedExamId(controlPlane, await succeededRunId(controlPlane));

    expect(sentinelSecretsIn(JSON.stringify(gateway.createdSpecs))).toEqual([
      SENTINEL_SECRETS.CLAUDE_CODE_OAUTH_TOKEN,
    ]);
  });

  /* @covers service:POL-001 */
  it("logs a failed examiner turn with the echoed secrets redacted", async () => {
    const controlPlane = examControlPlane();
    fakeExaminerInUse().answers(
      { kind: "output", output: openTurnOutput() },
      { kind: "exit", exitCode: 1, stderr: SECRET_ECHO },
    );
    const examId = await openedExamId(controlPlane, await succeededRunId(controlPlane));
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => undefined);

    await postStudentMessage(controlPlane, examId, { text: "B" });

    expect(errorLog.mock.calls).toEqual([
      [
        "exam.turn_failed",
        { exam_id: examId, exit_code: 1, stderr_tail: "proxy [redacted] rejected key [redacted]" },
      ],
    ]);
  });
});
