import { describe, expect, it } from "vitest";
import { CLOCK_START, controlPlaneWithFakeClock } from "../test-support/controlPlane";
import {
  getRun,
  jsonObjectOf,
  postRun,
  postWorker,
  serviceAuthorization,
  submittedRunId,
} from "../test-support/httpCalls";
import {
  insertActiveRun,
  lectureResult,
  storedFileId,
  succeededCompletion,
} from "../test-support/runArrangement";

const WATCH_URL = "https://www.youtube.com/watch?v=ZA-tUyM_y7s";

describe("POST /v1/runs", () => {
  /* @covers service:CON-001 */
  it.each([
    ["https://www.youtube.com/watch?v=ZA-tUyM_y7s", "ZA-tUyM_y7s"],
    ["https://m.youtube.com/watch?v=dQw4w9WgXcQ&list=PL590L5WQmH8f", "dQw4w9WgXcQ"],
    ["https://youtu.be/9bZkp7q19f0", "9bZkp7q19f0"],
    ["https://youtube.com/shorts/aqz-KE-bpKQ", "aqz-KE-bpKQ"],
    ["https://www.youtube.com/live/jfKfPfyJRdk", "jfKfPfyJRdk"],
    ["https://www.youtube.com/embed/M7lc1UVf-VE", "M7lc1UVf-VE"],
  ])("accepts %s as video %s", async (youtubeUrl, videoId) => {
    const controlPlane = controlPlaneWithFakeClock();

    const response = await postRun(controlPlane, { youtube_url: youtubeUrl });

    expect(response.status).toBe(202);
    expect(await jsonObjectOf(response)).toMatchObject({ status: "queued", video_id: videoId });
  });

  /* @covers service:CON-001 */
  it.each([
    "https://www.youtube.com/playlist?list=PL590L5WQmH8fJ54F369BLDSqIwcs-TCfs",
    "https://www.youtube.com/@veritasium",
    "https://www.youtube.com/channel/UCHnyfMqiRRG1u-2MsSQLbXA",
    "https://www.youtube.com/c/veritasium",
    "https://vimeo.com/76979871",
    "https://youtube.com.evil.test/watch?v=ZA-tUyM_y7s",
    "https://www.youtube.com/watch?v=too-short",
    "not a url",
  ])("rejects %s with INPUT_NOT_YOUTUBE", async (youtubeUrl) => {
    const controlPlane = controlPlaneWithFakeClock();

    const response = await postRun(controlPlane, { youtube_url: youtubeUrl });

    expect(response.status).toBe(422);
    expect(await jsonObjectOf(response)).toEqual({
      error: { code: "INPUT_NOT_YOUTUBE", message: "youtube_url is not a YouTube video URL" },
    });
  });

  /* @covers service:CON-001 */
  it("stores no run for a non-YouTube URL", async () => {
    const controlPlane = controlPlaneWithFakeClock();

    await postRun(controlPlane, { youtube_url: "https://vimeo.com/76979871" });

    expect(await controlPlane.run(async (ctx) => ctx.db.query("runs").collect())).toEqual([]);
  });

  /* @covers service:CON-001 */
  it.each([
    ["an array body", []],
    ["a numeric youtube_url", { youtube_url: 42 }],
    ["an unsupported lang", { youtube_url: WATCH_URL, lang: "de" }],
    ["a numeric external_ref", { youtube_url: WATCH_URL, external_ref: 7 }],
    ["an external_ref over 200 characters", { youtube_url: WATCH_URL, external_ref: "x".repeat(201) }],
  ])("rejects %s with INVALID_REQUEST", async (_case, body) => {
    const controlPlane = controlPlaneWithFakeClock();

    const response = await postRun(controlPlane, body);

    expect(response.status).toBe(422);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "INVALID_REQUEST" } });
  });

  /* @covers service:CON-001 */
  it("rejects malformed JSON with INVALID_REQUEST", async () => {
    const controlPlane = controlPlaneWithFakeClock();

    const response = await controlPlane.fetch("/v1/runs", {
      method: "POST",
      headers: serviceAuthorization(),
      body: "{\"youtube_url\":",
    });

    expect(response.status).toBe(422);
    expect(await jsonObjectOf(response)).toEqual({
      error: { code: "INVALID_REQUEST", message: "body is not valid JSON" },
    });
  });

  /* @covers service:CON-001 */
  it.each([
    ["a missing", {}],
    ["a wrong", { Authorization: "Bearer not-the-service-key" }],
  ])("answers 401 UNAUTHORIZED for %s API key", async (_case, headers) => {
    const controlPlane = controlPlaneWithFakeClock();

    const response = await postRun(controlPlane, { youtube_url: WATCH_URL }, headers);

    expect(response.status).toBe(401);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "UNAUTHORIZED" } });
  });

  /* @covers service:CON-001 */
  it("returns the first run for a repeated Idempotency-Key", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const headers = { ...serviceAuthorization(), "Idempotency-Key": "order-17" };
    const first = await jsonObjectOf(await postRun(controlPlane, { youtube_url: WATCH_URL }, headers));

    const repeated = await postRun(controlPlane, { youtube_url: "https://youtu.be/9bZkp7q19f0" }, headers);

    expect(repeated.status).toBe(202);
    expect(await jsonObjectOf(repeated)).toEqual(first);
  });
});

describe("GET /v1/runs/{run_id}", () => {
  /* @covers service:CON-001 */
  it("reports a submitted run as queued with its external_ref and no stages, error or spend", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const accepted = await jsonObjectOf(
      await postRun(controlPlane, { youtube_url: WATCH_URL, lang: "ru", external_ref: "e".repeat(200) }),
    );

    const response = await getRun(controlPlane, String(accepted.run_id));

    expect(response.status).toBe(200);
    expect(await jsonObjectOf(response)).toEqual({
      run_id: accepted.run_id,
      external_ref: "e".repeat(200),
      video_id: "ZA-tUyM_y7s",
      status: "queued",
      stages: [],
      error: null,
      llm_spend_usd: null,
      created_at: CLOCK_START.toISOString(),
      updated_at: CLOCK_START.toISOString(),
    });
  });

  /* @covers service:CON-001 */
  it("answers 401 UNAUTHORIZED for a wrong API key", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await submittedRunId(controlPlane, WATCH_URL);

    const response = await controlPlane.fetch(`/v1/runs/${runId}`, {
      headers: { Authorization: "Bearer not-the-service-key" },
    });

    expect(response.status).toBe(401);
  });

  /* @covers service:CON-001 */
  it("answers 404 RUN_NOT_FOUND for an unknown run", async () => {
    const controlPlane = controlPlaneWithFakeClock();

    const response = await getRun(controlPlane, "unknown-run");

    expect(response.status).toBe(404);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "RUN_NOT_FOUND" } });
  });
});

describe("GET /v1/runs/{run_id}/result", () => {
  /* @covers service:CON-001 */
  it("answers 404 RUN_NOT_FOUND for an unknown run", async () => {
    const controlPlane = controlPlaneWithFakeClock();

    const response = await getRun(controlPlane, "unknown-run/result");

    expect(response.status).toBe(404);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "RUN_NOT_FOUND" } });
  });

  /* @covers service:CON-001 */
  it("answers 409 RUN_NOT_FINISHED before the run succeeded", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await submittedRunId(controlPlane, WATCH_URL);

    const response = await getRun(controlPlane, `${runId}/result`);

    expect(response.status).toBe(409);
    expect(await jsonObjectOf(response)).toMatchObject({ error: { code: "RUN_NOT_FINISHED" } });
  });

  /* @covers service:CON-001 */
  it("returns the stored result of a succeeded run with file URLs", async () => {
    const controlPlane = controlPlaneWithFakeClock();
    const runId = await insertActiveRun(controlPlane, "run-token", "running");
    const pdfId = await storedFileId(controlPlane, "%PDF-1.7");
    const pdf = { kind: "pdf", name: "konspekt.pdf", size_bytes: 8, content_type: "application/pdf" };
    await postWorker(controlPlane, { runId, endpoint: "complete" }, "run-token", succeededCompletion([
      { ...pdf, storage_id: pdfId },
    ]));
    const pdfUrl = await controlPlane.run(async (ctx) => ctx.storage.getUrl(pdfId));
    const lecture = lectureResult();

    const response = await getRun(controlPlane, `${runId}/result`);

    expect(response.status).toBe(200);
    expect(await jsonObjectOf(response)).toEqual({
      run_id: runId,
      video: lecture.video,
      outline: lecture.outline,
      sections: lecture.sections,
      claims: lecture.claims,
      quiz: lecture.quiz,
      cut_log: lecture.cut_log,
      files: [{ ...pdf, url: pdfUrl }],
    });
  });
});
