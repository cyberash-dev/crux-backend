import { describe, expect, it, vi } from "vitest";
import type { FakeSandboxGateway } from "../test-support/FakeSandboxGateway";
import {
  CLOCK_START,
  type ControlPlane,
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
const PROXY_A = "http://proxy-user-a:proxy-pass-a@proxy-a.test:3128";
const PROXY_B = "http://proxy-user-b:proxy-pass-b@proxy-b.test:3128";
const PROXY_C = "http://proxy-user-c:proxy-pass-c@proxy-c.test:3128";
const BOT_CHECK_MESSAGE = "Sign in to confirm you're not a bot";

async function postBlockedDownload(controlPlane: ControlPlane, runId: string, token: string): Promise<Response> {
  return postWorker(controlPlane, { runId, endpoint: "complete" }, token, {
    status: "failed",
    error: { code: "DOWNLOAD_BLOCKED", message: BOT_CHECK_MESSAGE },
  });
}

async function finishRunsOneAfterAnother(
  controlPlane: ControlPlane,
  gateway: FakeSandboxGateway,
  runIds: readonly string[],
): Promise<void> {
  for (const runId of runIds) {
    await runScheduledFunctions(controlPlane);
    await postWorker(controlPlane, { runId, endpoint: "complete" }, gateway.runToken(runId), {
      status: "failed",
      error: { code: "VIDEO_UNAVAILABLE", message: "video is private" },
    });
  }
}

function proxiesOfCreatedSandboxes(gateway: FakeSandboxGateway): string[] {
  return gateway.createdSpecs.map((spec) => spec.outboundProxyUrl);
}

function proxiesOfRun(gateway: FakeSandboxGateway, runId: string): string[] {
  return gateway.createdSpecs
    .filter((spec) => spec.labels.run_id === runId)
    .map((spec) => spec.outboundProxyUrl);
}

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

describe("proxy rotation", () => {
  /* @covers service:REQ-001 */
  /* @covers service:EXT-001 */
  /* @covers service:DLT-009 */
  it("gives consecutive sandbox creations consecutive proxies of PROXY_URL, wrapping around", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B, PROXY_C].join(","));
    const gateway = fakeGatewayInUse();
    const runIds = [
      await submittedRunId(controlPlane, FIRST_URL),
      await submittedRunId(controlPlane, SECOND_URL),
      await submittedRunId(controlPlane, THIRD_URL),
      await submittedRunId(controlPlane, FIRST_URL),
    ];

    await finishRunsOneAfterAnother(controlPlane, gateway, runIds);

    expect(proxiesOfCreatedSandboxes(gateway)).toEqual([PROXY_A, PROXY_B, PROXY_C, PROXY_A]);
  });

  /* @covers service:EXT-001 */
  /* @covers service:DLT-009 */
  it("takes a proxy URL without the blanks and empty entries around it", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", ` , ${PROXY_A} ,`);
    const gateway = fakeGatewayInUse();
    await submittedRunId(controlPlane, FIRST_URL);

    await runScheduledFunctions(controlPlane);

    expect(proxiesOfCreatedSandboxes(gateway)).toEqual([PROXY_A]);
  });

  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("fails the run naming PROXY_URL when the list holds no URL", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", " , ");
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);

    await runScheduledFunctions(controlPlane);

    expect((await runStatusOf(controlPlane, runId)).error).toEqual({
      code: "SANDBOX_START_FAILED",
      message: "control-plane env not set: PROXY_URL",
    });
    expect(gateway.createdSpecs).toEqual([]);
  });
});

describe("blocked download", () => {
  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("provisions the run again in a new sandbox with the next proxy", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B, PROXY_C].join(","));
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);

    await postBlockedDownload(controlPlane, runId, gateway.runToken(runId));
    await runScheduledFunctions(controlPlane);

    expect(gateway.createdSpecs.map((spec) => [spec.labels.run_id, spec.outboundProxyUrl])).toEqual([
      [runId, PROXY_A],
      [runId, PROXY_B],
    ]);
  });

  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("gives the blocked run a proxy it has not tried while another run took the turn in between", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("MAX_PARALLEL_RUNS", "2");
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const blockedRunId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    await submittedRunId(controlPlane, SECOND_URL);
    await runScheduledFunctions(controlPlane);

    await postBlockedDownload(controlPlane, blockedRunId, gateway.runToken(blockedRunId));
    await runScheduledFunctions(controlPlane);

    expect(proxiesOfRun(gateway, blockedRunId)).toEqual([PROXY_A, PROXY_B]);
  });

  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("continues the rotation after the turn the blocked run took past its blocked proxy", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("MAX_PARALLEL_RUNS", "2");
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const blockedRunId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    const finishingRunId = await submittedRunId(controlPlane, SECOND_URL);
    await runScheduledFunctions(controlPlane);
    await submittedRunId(controlPlane, THIRD_URL);
    await postBlockedDownload(controlPlane, blockedRunId, gateway.runToken(blockedRunId));
    await runScheduledFunctions(controlPlane);

    await postWorker(controlPlane, { runId: finishingRunId, endpoint: "complete" }, gateway.runToken(finishingRunId), {
      status: "failed",
      error: { code: "VIDEO_UNAVAILABLE", message: "video is private" },
    });
    await runScheduledFunctions(controlPlane);

    expect(proxiesOfCreatedSandboxes(gateway)).toEqual([PROXY_A, PROXY_B, PROXY_B, PROXY_A]);
  });

  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("deletes the sandbox whose download was blocked", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);

    await postBlockedDownload(controlPlane, runId, gateway.runToken(runId));
    await runScheduledFunctions(controlPlane);

    expect(gateway.deletedSandboxIds).toEqual(["sandbox-1"]);
  });

  /* @covers service:DLT-009 */
  /* @covers service:POL-001 */
  it("rejects the token of the blocked worker with 401", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    const blockedToken = gateway.runToken(runId);
    await postBlockedDownload(controlPlane, runId, blockedToken);
    await runScheduledFunctions(controlPlane);

    const response = await postWorker(controlPlane, { runId, endpoint: "events" }, blockedToken, { type: "heartbeat" });

    expect(response.status).toBe(401);
  });

  /* @covers service:DLT-009 */
  it("moves the run to running when the worker of the new sandbox reports", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    await postBlockedDownload(controlPlane, runId, gateway.runToken(runId));
    await runScheduledFunctions(controlPlane);

    await postWorker(controlPlane, { runId, endpoint: "events" }, gateway.runToken(runId), { type: "heartbeat" });

    expect((await runStatusOf(controlPlane, runId)).status).toBe("running");
  });

  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("keeps the blocked run's place among the active runs", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const blockedRunId = await submittedRunId(controlPlane, FIRST_URL);
    const waitingRunId = await submittedRunId(controlPlane, SECOND_URL);
    await runScheduledFunctions(controlPlane);

    await postBlockedDownload(controlPlane, blockedRunId, gateway.runToken(blockedRunId));
    await runScheduledFunctions(controlPlane);

    expect([
      (await runStatusOf(controlPlane, blockedRunId)).status,
      (await runStatusOf(controlPlane, waitingRunId)).status,
    ]).toEqual(["provisioning", "queued"]);
  });

  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("gives the provisioned-again run a fresh 15-minute watchdog window", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(CLOCK_START.getTime() + 14 * MINUTE_MS);
    await postBlockedDownload(controlPlane, runId, gateway.runToken(runId));
    await runScheduledFunctions(controlPlane);
    vi.setSystemTime(CLOCK_START.getTime() + 16 * MINUTE_MS);

    await controlPlane.mutation(internal.watchdog.failSilentRuns, {});

    expect((await runStatusOf(controlPlane, runId)).status).toBe("provisioning");
  });

  /* @covers service:REQ-001 */
  /* @covers service:CON-001 */
  /* @covers service:DLT-009 */
  it("fails the run with DOWNLOAD_BLOCKED and the worker's message once every proxy blocked it", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    vi.stubEnv("PROXY_URL", [PROXY_A, PROXY_B].join(","));
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);
    await postBlockedDownload(controlPlane, runId, gateway.runToken(runId));
    await runScheduledFunctions(controlPlane);

    await postBlockedDownload(controlPlane, runId, gateway.runToken(runId));

    expect(await runStatusOf(controlPlane, runId)).toMatchObject({
      status: "failed",
      error: { code: "DOWNLOAD_BLOCKED", message: BOT_CHECK_MESSAGE },
    });
  });

  /* @covers service:REQ-001 */
  /* @covers service:DLT-009 */
  it("fails a run with a one-URL PROXY_URL at its first block without a second sandbox", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const gateway = fakeGatewayInUse();
    const runId = await submittedRunId(controlPlane, FIRST_URL);
    await runScheduledFunctions(controlPlane);

    await postBlockedDownload(controlPlane, runId, gateway.runToken(runId));
    await runScheduledFunctions(controlPlane);

    expect((await runStatusOf(controlPlane, runId)).error).toMatchObject({ code: "DOWNLOAD_BLOCKED" });
    expect(gateway.createdSpecs).toHaveLength(1);
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
