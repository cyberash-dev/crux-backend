import { describe, expect, it, vi } from "vitest";
import {
  CLOCK_START,
  controlPlaneWithFakeClock,
  runScheduledFunctions,
  SENTINEL_SECRETS,
  WORKER_API_BASE,
  WORKER_SNAPSHOT,
} from "../test-support/controlPlane";
import { fakeGatewayInUse } from "../test-support/fakeGatewayInUse";
import { postWorker, runStatusOf, submittedRunId } from "../test-support/httpCalls";
import { storedFileId, storedRunId, succeededCompletion } from "../test-support/runArrangement";
import { internal } from "./_generated/api";

vi.mock("./sandbox/daytonaGatewayFactory", () => ({ daytonaSandboxGateway: vi.fn() }));

const FIRST_URL = "https://www.youtube.com/watch?v=ZA-tUyM_y7s";
const SECOND_URL = "https://youtu.be/9bZkp7q19f0";
const THIRD_URL = "https://youtube.com/shorts/aqz-KE-bpKQ";
const MINUTE_MS = 60 * 1000;

describe("run queue", () => {
  /* @covers service:REQ-001 */
  it.each([
    ["1", ["provisioning", "queued", "queued"]],
    ["2", ["provisioning", "provisioning", "queued"]],
  ])("with MAX_PARALLEL_RUNS=%s provisions the oldest runs only", async (limit, expectedStatuses) => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("MAX_PARALLEL_RUNS", limit);
    fakeGatewayInUse();
    const runIds = [
      await submittedRunId(controlPlane, FIRST_URL),
      await submittedRunId(controlPlane, SECOND_URL),
      await submittedRunId(controlPlane, THIRD_URL),
    ];

    await runScheduledFunctions(controlPlane);

    const statuses = await Promise.all(
      runIds.map(async (runId) => (await runStatusOf(controlPlane, runId)).status),
    );
    expect(statuses).toEqual(expectedStatuses);
  });

  /* @covers service:REQ-001 */
  it("provisions the next queued run once the active run finishes", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const firstRunId = await submittedRunId(controlPlane, FIRST_URL);
    const secondRunId = await submittedRunId(controlPlane, SECOND_URL);
    await runScheduledFunctions(controlPlane);

    await postWorker(controlPlane, { runId: firstRunId, endpoint: "complete" }, gateway.runToken(firstRunId), {
      status: "failed",
      error: { code: "VIDEO_UNAVAILABLE", message: "video is private" },
    });
    await runScheduledFunctions(controlPlane);

    expect((await runStatusOf(controlPlane, secondRunId)).status).toBe("provisioning");
  });
});

describe("provisioning", () => {
  /* @covers service:REQ-001 */
  /* @covers service:EXT-001 */
  it("creates the sandbox from the snapshot with the proxy, worker variables and credentials", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, "https://youtu.be/9bZkp7q19f0", "ru");

    await runScheduledFunctions(controlPlane);

    expect(gateway.specFor(runId)).toEqual({
      snapshot: WORKER_SNAPSHOT,
      outboundProxyUrl: SENTINEL_SECRETS.PROXY_URL,
      labels: { run_id: runId },
      envVars: {
        KONSPEKT_RUN_ID: runId,
        KONSPEKT_API_BASE: WORKER_API_BASE,
        KONSPEKT_RUN_TOKEN: gateway.runToken(runId),
        KONSPEKT_YOUTUBE_URL: "https://www.youtube.com/watch?v=9bZkp7q19f0",
        KONSPEKT_LANG: "ru",
        CLAUDE_CODE_OAUTH_TOKEN: SENTINEL_SECRETS.CLAUDE_CODE_OAUTH_TOKEN,
        ELEVENLABS_API_KEY: SENTINEL_SECRETS.ELEVENLABS_API_KEY,
        EXA_API_KEY: SENTINEL_SECRETS.EXA_API_KEY,
      },
    });
  });

  /* @covers service:REQ-001 */
  it("starts the worker in the created sandbox", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    await submittedRunId(controlPlane, FIRST_URL);

    await runScheduledFunctions(controlPlane);

    expect(gateway.startedSandboxIds).toEqual(["sandbox-1"]);
  });

  /* @covers service:REQ-001 */
  it("moves the run to running when the started worker reports", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);

    await postWorker(controlPlane, { runId, endpoint: "events" }, gateway.runToken(runId), {
      type: "stage_completed",
      stage: "download",
    });

    expect((await runStatusOf(controlPlane, runId)).status).toBe("running");
  });

  /* @covers service:REQ-001 */
  it("starts no second sandbox when provisioning repeats for the same run", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await storedRunId(controlPlane, await submittedRunId(controlPlane, FIRST_URL));
    await runScheduledFunctions(controlPlane);

    await controlPlane.action(internal.provisioning.provisionRun, { runId });

    expect(gateway.createdSpecs).toHaveLength(1);
  });

  /* @covers service:REQ-001 */
  it("fails the run with SANDBOX_START_FAILED when sandbox creation fails", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    fakeGatewayInUse({ operation: "create", message: "organization quota exceeded" });
    const runId = await submittedRunId(controlPlane, FIRST_URL);

    await runScheduledFunctions(controlPlane);

    expect(await runStatusOf(controlPlane, runId)).toMatchObject({
      status: "failed",
      error: { code: "SANDBOX_START_FAILED", message: "sandbox create failed: organization quota exceeded" },
    });
  });

  /* @covers service:REQ-001 */
  it("deletes the sandbox when the worker cannot be started", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse({ operation: "start", message: "session refused" });
    const runId = await submittedRunId(controlPlane, FIRST_URL);

    await runScheduledFunctions(controlPlane);

    expect((await runStatusOf(controlPlane, runId)).error).toMatchObject({ code: "SANDBOX_START_FAILED" });
    expect(gateway.deletedSandboxIds).toEqual(["sandbox-1"]);
  });

  /* @covers service:REQ-001 */
  it("fails the run naming WORKER_SNAPSHOT when it is not configured", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("WORKER_SNAPSHOT", "");
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);

    await runScheduledFunctions(controlPlane);

    expect((await runStatusOf(controlPlane, runId)).error).toEqual({
      code: "SANDBOX_START_FAILED",
      message: "control-plane env not set: WORKER_SNAPSHOT",
    });
    expect(gateway.createdSpecs).toEqual([]);
  });
});

describe("completion", () => {
  /* @covers service:REQ-001 */
  it("stores the result of a success completion", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    const markdownId = await storedFileId(controlPlane, "# Lecture 1");

    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), succeededCompletion([
      { kind: "markdown", name: "konspekt.md", storage_id: markdownId, size_bytes: 11, content_type: "text/markdown" },
    ]));

    expect((await runStatusOf(controlPlane, runId)).status).toBe("succeeded");
  });

  /* @covers service:REQ-001 */
  it("deletes the sandbox after a success completion", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), succeededCompletion([]));

    await runScheduledFunctions(controlPlane);

    expect(gateway.deletedSandboxIds).toEqual(["sandbox-1"]);
  });
});

describe("silent worker watchdog", () => {
  /* @covers service:REQ-001 */
  it("fails a run without worker events for 15 minutes with WORKER_LOST", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(CLOCK_START.getTime() + 15 * MINUTE_MS + 1);

    await controlPlane.mutation(internal.watchdog.failSilentRuns, {});

    expect(await runStatusOf(controlPlane, runId)).toMatchObject({
      status: "failed",
      error: { code: "WORKER_LOST" },
    });
  });

  /* @covers service:REQ-001 */
  it("deletes the sandbox of a run lost to the watchdog", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(CLOCK_START.getTime() + 15 * MINUTE_MS + 1);

    await controlPlane.mutation(internal.watchdog.failSilentRuns, {});
    await runScheduledFunctions(controlPlane);

    expect(gateway.deletedSandboxIds).toEqual(["sandbox-1"]);
  });

  /* @covers service:REQ-001 */
  it("keeps a running run whose last heartbeat is recent", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(CLOCK_START.getTime() + 10 * MINUTE_MS);
    await postWorker(controlPlane, { runId, endpoint: "events" }, gateway.runToken(runId), { type: "heartbeat" });
    vi.setSystemTime(CLOCK_START.getTime() + 20 * MINUTE_MS);

    await controlPlane.mutation(internal.watchdog.failSilentRuns, {});

    expect((await runStatusOf(controlPlane, runId)).status).toBe("running");
  });
});
