import { internal } from "./_generated/api";
import { type ActionCtx, httpAction } from "./_generated/server";
import { bearerToken } from "./httpBoundary/bearerToken";
import { type Completion, completionRequest } from "./httpBoundary/completionRequest";
import { jsonBody } from "./httpBoundary/jsonBody";
import {
  errorResponse,
  invalidRequestResponse,
  jsonResponse,
  noContentResponse,
  notFoundResponse,
  unauthorizedResponse,
} from "./httpBoundary/responses";
import { workerRoute } from "./httpBoundary/routes";
import { MAX_UPLOAD_BYTES, uploadUrlRequest } from "./httpBoundary/uploadUrlRequest";
import { workerEventRequest } from "./httpBoundary/workerEventRequest";
import { sha256Hex } from "./security/sha256";
import type { WorkerCallOutcome } from "./workerRuns";

type WorkerCall = { runId: string; tokenHash: string };

export const workerRequest = httpAction(async (ctx, request) => {
  const route = workerRoute(new URL(request.url).pathname);
  if (route === null) {
    return notFoundResponse();
  }
  const token = bearerToken(request);
  if (token === null) {
    return unauthorizedResponse();
  }
  const call = { runId: route.runId, tokenHash: await sha256Hex(token) };
  const access = await ctx.runQuery(internal.workerRuns.workerAccessKind, call);
  if (access !== "granted") {
    return outcomeResponse(access);
  }
  const body = await jsonBody(request);
  if (body.kind === "malformed") {
    return invalidRequestResponse("body is not valid JSON");
  }
  switch (route.endpoint) {
    case "events":
      return respondToEvent(ctx, call, body.value);
    case "upload-url":
      return respondToUploadRequest(ctx, body.value);
    case "complete":
      return respondToCompletion(ctx, call, body.value);
  }
});

async function respondToEvent(ctx: ActionCtx, call: WorkerCall, body: unknown): Promise<Response> {
  const event = workerEventRequest(body);
  if (event.kind === "invalid") {
    return invalidRequestResponse(event.message);
  }
  const outcome = await ctx.runMutation(internal.workerRuns.recordEvent, { ...call, event: event.value });
  return outcomeResponse(outcome);
}

async function respondToUploadRequest(ctx: ActionCtx, body: unknown): Promise<Response> {
  const upload = uploadUrlRequest(body);
  if (upload.kind === "invalid") {
    return invalidRequestResponse(upload.message);
  }
  if (upload.value.sizeBytes > MAX_UPLOAD_BYTES) {
    return errorResponse(413, "UPLOAD_TOO_LARGE", "size_bytes exceeds 50 MB");
  }
  return jsonResponse(200, { upload_url: await ctx.storage.generateUploadUrl() });
}

async function respondToCompletion(ctx: ActionCtx, call: WorkerCall, body: unknown): Promise<Response> {
  const completion = completionRequest(body);
  if (completion.kind === "invalid") {
    return invalidRequestResponse(completion.message);
  }
  return outcomeResponse(await recordCompletion(ctx, call, completion.value));
}

async function recordCompletion(
  ctx: ActionCtx,
  call: WorkerCall,
  completion: Completion,
): Promise<WorkerCallOutcome> {
  if (completion.status === "failed") {
    return ctx.runMutation(internal.workerRuns.recordFailure, { ...call, error: completion.error });
  }
  const { result, files } = completion;
  return ctx.runMutation(internal.workerRuns.recordSuccess, {
    ...call,
    video: result.video,
    outline_json: JSON.stringify(result.outline),
    section_jsons: result.sections.map((section) => JSON.stringify(section)),
    claims_json: JSON.stringify(result.claims),
    quiz_json: JSON.stringify(result.quiz),
    cut_log_json: JSON.stringify(result.cutLog),
    llm_spend_usd: result.llmSpendUsd,
    files: [...files],
  });
}

function outcomeResponse(outcome: WorkerCallOutcome): Response {
  switch (outcome) {
    case "applied":
      return noContentResponse();
    case "unauthorized":
      return unauthorizedResponse();
    case "terminal":
      return errorResponse(409, "RUN_TERMINAL", "run already has a terminal status");
    case "unknown_storage_id":
      return invalidRequestResponse("a file storage_id does not refer to an uploaded file");
  }
}
