import { describe, expect, it, vi } from "vitest";
import {
  CLOCK_START,
  controlPlaneWithFakeClock,
  runScheduledFunctions,
  SENTINEL_SECRETS,
} from "../test-support/controlPlane";
import { FakeOperatorChat } from "../test-support/FakeOperatorChat";
import { fakeGatewayInUse } from "../test-support/fakeGatewayInUse";
import { jsonObjectOf, postRun, postWorker, serviceAuthorization, submittedRunId } from "../test-support/httpCalls";
import { operatorChatInUse } from "../test-support/operatorChatArrangement";
import { succeededCompletion } from "../test-support/runArrangement";
import { internal } from "./_generated/api";

vi.mock("./sandbox/daytonaGatewayFactory", () => ({ daytonaSandboxGateway: vi.fn() }));
vi.mock("./operatorChat/operatorChatFactory", () => ({ telegramOperatorChat: vi.fn() }));

const START = CLOCK_START.getTime();
const MINUTE_MS = 60 * 1000;
const FIRST_URL = "https://www.youtube.com/watch?v=ZA-tUyM_y7s";
const SECOND_URL = "https://www.youtube.com/watch?v=9bZkp7q19f0";
const THIRD_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ";
const NOTICE_PROXY_A = "http://notice-user-a:notice-pass-a@disp.proxy.test:8001";
const NOTICE_PROXY_B = "http://notice-user-b:notice-pass-b@disp.proxy.test:8002";

function newRunNotice(runId: string, queuedAhead: number, activeRuns: number): string {
  return `New run ${runId}: ${FIRST_URL}. Queued ahead: ${queuedAhead}. Active: ${activeRuns}/1.`;
}

describe("run notices", () => {
  /* @covers service:REQ-006 */
  it("sends one message per new run with its URL, run id, external_ref and queue numbers", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    fakeGatewayInUse();
    const firstRunId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    const secondRunId = await submittedRunId(controlPlane, SECOND_URL);

    const thirdResponse = await postRun(controlPlane, {
      youtube_url: THIRD_URL,
      lang: "auto",
      external_ref: "course-7/lecture-3",
    });
    await runScheduledFunctions(controlPlane);

    const thirdRunId = String((await jsonObjectOf(thirdResponse)).run_id);
    expect(chat.sentTexts).toEqual([
      `New run ${firstRunId}: ${FIRST_URL}. Queued ahead: 0. Active: 0/1.`,
      `New run ${secondRunId}: ${SECOND_URL}. Queued ahead: 0. Active: 1/1.`,
      `New run ${thirdRunId}: ${THIRD_URL} (ref: course-7/lecture-3). Queued ahead: 1. Active: 1/1.`,
    ]);
  });

  /* @covers service:REQ-006 */
  it("sends no message for an idempotent resubmission that returns the existing run", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    fakeGatewayInUse();
    const headers = { ...serviceAuthorization(), "Idempotency-Key": "lecture-1" };
    const firstResponse = await postRun(controlPlane, { youtube_url: FIRST_URL }, headers);
    await runScheduledFunctions(controlPlane);

    await postRun(controlPlane, { youtube_url: FIRST_URL }, headers);
    await runScheduledFunctions(controlPlane);

    const runId = String((await jsonObjectOf(firstResponse)).run_id);
    expect(chat.sentTexts).toEqual([newRunNotice(runId, 0, 0)]);
  });

  /* @covers service:REQ-006 */
  it("answers the submission before the new-run message is sent", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    fakeGatewayInUse();

    const response = await postRun(controlPlane, { youtube_url: FIRST_URL });

    expect({ status: response.status, sentTexts: chat.sentTexts }).toEqual({ status: 202, sentTexts: [] });
  });

  /* @covers service:REQ-006 */
  it("sends one message with the title and whole minutes when a run succeeds", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(START + 17 * MINUTE_MS + 50 * 1000);

    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), succeededCompletion([]));
    await runScheduledFunctions(controlPlane);

    expect(chat.sentTexts).toEqual([
      newRunNotice(runId, 0, 0),
      `Run ${runId} succeeded in 17 min: Lecture 1 ${FIRST_URL}`,
    ]);
  });

  /* @covers service:REQ-006 */
  it("sends one message with the code, the redacted message cut to 200 characters and minutes when a run fails", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(START + 3 * MINUTE_MS);

    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), {
      status: "failed",
      error: { code: "PIPELINE_FAILED", message: `exa rejected ${SENTINEL_SECRETS.EXA_API_KEY}: ${"x".repeat(300)}` },
    });
    await runScheduledFunctions(controlPlane);

    const cutMessage = `exa rejected [redacted]: ${"x".repeat(175)}`;
    expect(chat.sentTexts).toEqual([
      newRunNotice(runId, 0, 0),
      `Run ${runId} failed after 3 min with PIPELINE_FAILED: ${cutMessage} ${FIRST_URL}`,
    ]);
  });

  /* @covers service:REQ-006 */
  it("sends one finish message when a sandbox fails to start", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    fakeGatewayInUse({ operation: "create", message: "quota exceeded" });
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const runId = await submittedRunId(controlPlane, FIRST_URL);

    await runScheduledFunctions(controlPlane);

    expect(chat.sentTexts).toEqual([
      newRunNotice(runId, 0, 0),
      `Run ${runId} failed after 0 min with SANDBOX_START_FAILED: sandbox create failed: quota exceeded ${FIRST_URL}`,
    ]);
  });

  /* @covers service:REQ-006 */
  it("sends one finish message when the watchdog fails a silent run", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(START + 16 * MINUTE_MS);

    await controlPlane.mutation(internal.watchdog.failSilentRuns, {});
    await runScheduledFunctions(controlPlane);

    expect(chat.sentTexts).toEqual([
      newRunNotice(runId, 0, 0),
      `Run ${runId} failed after 16 min with WORKER_LOST: no worker event for 15 minutes ${FIRST_URL}`,
    ]);
  });

  /* @covers service:REQ-006 */
  it("sends no second finish message when a finished run is completed again", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const chat = operatorChatInUse();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    const failedCompletion = { status: "failed", error: { code: "DOWNLOAD_FAILED", message: "HTTP 403" } };
    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), failedCompletion);

    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), failedCompletion);
    await runScheduledFunctions(controlPlane);

    expect(chat.sentTexts).toEqual([
      newRunNotice(runId, 0, 0),
      `Run ${runId} failed after 0 min with DOWNLOAD_FAILED: HTTP 403 ${FIRST_URL}`,
    ]);
  });

  /* @covers service:REQ-006 */
  it("sends no finish message when a DOWNLOAD_BLOCKED completion provisions the run again", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", `${NOTICE_PROXY_A},${NOTICE_PROXY_B}`);
    const chat = operatorChatInUse();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);

    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), {
      status: "failed",
      error: { code: "DOWNLOAD_BLOCKED", message: "Sign in to confirm you're not a bot" },
    });
    await runScheduledFunctions(controlPlane);

    expect(chat.sentTexts).toEqual([newRunNotice(runId, 0, 0), "Proxies: 1/2 OK. Blocked: port 8001."]);
  });

  /* @covers service:REQ-006 */
  it.each(["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])(
    "sends nothing and logs a warning for a new run when %s is missing",
    async (missingEnvName) => {
      const controlPlane = controlPlaneWithFakeClock();
      const chat = operatorChatInUse();
      vi.stubEnv(missingEnvName, "");
      fakeGatewayInUse();
      const warningLog = vi.spyOn(console, "warn").mockImplementation(() => undefined);

      await submittedRunId(controlPlane, FIRST_URL);
      await runScheduledFunctions(controlPlane);

      expect({ sentTexts: chat.sentTexts, warnings: warningLog.mock.calls }).toEqual({
        sentTexts: [],
        warnings: [["telegram.not_configured", { missing_env: [missingEnvName], dropped_messages: 1 }]],
      });
    },
  );

  /* @covers service:REQ-006 */
  it("logs a Telegram error for a new-run message without the bot token", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    operatorChatInUse(new FakeOperatorChat(`HTTP 401: Unauthorized for ${SENTINEL_SECRETS.TELEGRAM_BOT_TOKEN}`));
    fakeGatewayInUse();
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => undefined);

    await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);

    expect(errorLog.mock.calls).toEqual([
      ["telegram.send_failed", { message: "telegram sendMessage failed: HTTP 401: Unauthorized for [redacted]" }],
    ]);
  });
});
