import { describe, expect, it } from "vitest";
import { CLOCK_START, controlPlaneWithFakeClock } from "../test-support/controlPlane";
import { jsonObjectOf, postWorker, runStatusOf, type WorkerEndpoint } from "../test-support/httpCalls";
import {
  insertActiveRun,
  storedFileId,
  succeededCompletion,
} from "../test-support/runArrangement";

const FIFTY_MEGABYTES = 50 * 1024 * 1024;

function pdfFile(storageId: string): Record<string, unknown> {
  return { kind: "pdf", name: "konspekt.pdf", storage_id: storageId, size_bytes: 8, content_type: "application/pdf" };
}

describe("POST /worker/runs/{run_id}/events", () => {
  /* @covers service:CON-002 */
  it("records a completed stage reported with the run's token", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a");

    const response = await postWorker(controlPlane, { runId, endpoint: "events" }, "token-a", {
      type: "stage_completed",
      stage: "download",
    });

    expect(response.status).toBe(204);
    expect((await runStatusOf(controlPlane, runId)).stages).toEqual([
      { name: "download", completed_at: CLOCK_START.toISOString() },
    ]);
  });

  /* @covers service:CON-002 */
  it("moves a provisioning run to running on its first event", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a", "provisioning");

    await postWorker(controlPlane, { runId, endpoint: "events" }, "token-a", { type: "heartbeat" });

    expect((await runStatusOf(controlPlane, runId)).status).toBe("running");
  });

  /* @covers service:CON-002 */
  it("records a repeated stage once", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a", "running");
    const event = { type: "stage_completed", stage: "ingest" };
    await postWorker(controlPlane, { runId, endpoint: "events" }, "token-a", event);

    await postWorker(controlPlane, { runId, endpoint: "events" }, "token-a", event);

    expect((await runStatusOf(controlPlane, runId)).stages).toEqual([
      { name: "ingest", completed_at: CLOCK_START.toISOString() },
    ]);
  });

  /* @covers service:CON-002 */
  it.each([
    ["an unknown stage", { type: "stage_completed", stage: "upload" }],
    ["an unknown event type", { type: "progress" }],
    ["a non-object body", ["heartbeat"]],
  ])("rejects %s with 422", async (_case, body) => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a");

    const response = await postWorker(controlPlane, { runId, endpoint: "events" }, "token-a", body);

    expect(response.status).toBe(422);
  });
});

describe("worker authentication", () => {
  /* @covers service:CON-002 */
  /* @covers service:POL-001 */
  it.each<WorkerEndpoint>(["events", "upload-url", "complete"])(
    "rejects another run's token on %s with 401",
    async (endpoint) => {
      const controlPlane = controlPlaneWithFakeClock();
      const runId = await insertActiveRun(controlPlane, "token-a");
      await insertActiveRun(controlPlane, "token-b");

      const response = await postWorker(controlPlane, { runId, endpoint }, "token-b", { type: "heartbeat" });

      expect(response.status).toBe(401);
      expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "UNAUTHORIZED" } });
    },
  );

  /* @covers service:CON-002 */
  it("rejects a call without a token with 401", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a");

    const response = await controlPlane.fetch(`/worker/runs/${runId}/events`, {
      method: "POST",
      body: JSON.stringify({ type: "heartbeat" }),
    });

    expect(response.status).toBe(401);
  });
});

describe("POST /worker/runs/{run_id}/upload-url", () => {
  /* @covers service:CON-002 */
  it("answers 413 for an upload over 50 MB", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a");

    const response = await postWorker(controlPlane, { runId, endpoint: "upload-url" }, "token-a", {
      name: "konspekt.pdf",
      content_type: "application/pdf",
      size_bytes: FIFTY_MEGABYTES + 1,
    });

    expect(response.status).toBe(413);
  });

  /* @covers service:CON-002 */
  it("returns a storage upload URL for a file of exactly 50 MB", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a");

    const response = await postWorker(controlPlane, { runId, endpoint: "upload-url" }, "token-a", {
      name: "konspekt.pdf",
      content_type: "application/pdf",
      size_bytes: FIFTY_MEGABYTES,
    });

    expect(response.status).toBe(200);
    expect(typeof (await jsonObjectOf(response)).upload_url).toBe("string");
  });
});

describe("POST /worker/runs/{run_id}/complete", () => {
  /* @covers service:CON-002 */
  it("stores a success completion together with the succeeded status and spend", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a", "running");
    const pdfId = await storedFileId(controlPlane, "%PDF-1.7");

    const response = await postWorker(
      controlPlane,
      { runId, endpoint: "complete" },
      "token-a",
      succeededCompletion([pdfFile(pdfId)]),
    );

    expect(response.status).toBe(204);
    expect(await runStatusOf(controlPlane, runId)).toMatchObject({
      status: "succeeded",
      llm_spend_usd: 1.25,
      error: null,
    });
  });

  /* @covers service:CON-002 */
  it("stores nothing and keeps the run active when a file was never uploaded", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a", "running");
    const pdfId = await storedFileId(controlPlane, "%PDF-1.7");
    await controlPlane.run(async (ctx) => ctx.storage.delete(pdfId));

    const response = await postWorker(
      controlPlane,
      { runId, endpoint: "complete" },
      "token-a",
      succeededCompletion([pdfFile(pdfId)]),
    );

    expect(response.status).toBe(422);
    expect((await runStatusOf(controlPlane, runId)).status).toBe("running");
    expect(
      await controlPlane.run(async (ctx) => [
        ...(await ctx.db.query("run_results").collect()),
        ...(await ctx.db.query("run_sections").collect()),
        ...(await ctx.db.query("run_files").collect()),
      ]),
    ).toEqual([]);
  });

  /* @covers service:CON-002 */
  it("records a worker-reported failure with its code and message", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a", "running");

    await postWorker(controlPlane, { runId, endpoint: "complete" }, "token-a", {
      status: "failed",
      error: { code: "PIPELINE_FAILED", message: "konspekt build exited with 1" },
    });

    expect(await runStatusOf(controlPlane, runId)).toMatchObject({
      status: "failed",
      error: { code: "PIPELINE_FAILED", message: "konspekt build exited with 1" },
    });
  });

  /* @covers service:CON-002 */
  it.each([
    ["a missing result", { status: "succeeded", files: [] }],
    ["sections that are not objects", { status: "succeeded", files: [], result: { sections: ["s1"] } }],
    ["an unknown failure code", { status: "failed", error: { code: "OOPS", message: "x" } }],
    ["an unknown status", { status: "done" }],
  ])("rejects %s with 422", async (_case, body) => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a", "running");

    const response = await postWorker(controlPlane, { runId, endpoint: "complete" }, "token-a", body);

    expect(response.status).toBe(422);
  });
});

describe("calls after a terminal status", () => {
  /* @covers service:CON-002 */
  it.each<[WorkerEndpoint, unknown]>([
    ["events", { type: "heartbeat" }],
    ["upload-url", { name: "konspekt.md", content_type: "text/markdown", size_bytes: 10 }],
    ["complete", { status: "failed", error: { code: "PIPELINE_FAILED", message: "again" } }],
  ])("answers 409 on %s", async (endpoint, body) => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "token-a", "running");
    await postWorker(controlPlane, { runId, endpoint: "complete" }, "token-a", {
      status: "failed",
      error: { code: "DOWNLOAD_FAILED", message: "HTTP 403" },
    });

    const response = await postWorker(controlPlane, { runId, endpoint }, "token-a", body);

    expect(response.status).toBe(409);
  });
});
