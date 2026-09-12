import { internal } from "./_generated/api";
import { type ActionCtx, httpAction } from "./_generated/server";
import { jsonBody } from "./httpBoundary/jsonBody";
import {
  errorResponse,
  invalidRequestResponse,
  jsonResponse,
  notFoundResponse,
  unauthorizedResponse,
} from "./httpBoundary/responses";
import { resultBody } from "./httpBoundary/resultBody";
import { clientReadRoute } from "./httpBoundary/routes";
import { isServiceCaller } from "./httpBoundary/serviceAuth";
import { type SubmitRunRequest, submitRunRequest } from "./httpBoundary/submitRunRequest";
import { canonicalWatchUrl, youtubeVideoId } from "./httpBoundary/youtubeUrl";

export const submitRun = httpAction(async (ctx, request) => {
  if (!(await isServiceCaller(request))) {
    return unauthorizedResponse();
  }
  const body = await jsonBody(request);
  if (body.kind === "malformed") {
    return invalidRequestResponse("body is not valid JSON");
  }
  const submission = submitRunRequest(body.value);
  if (submission.kind === "invalid") {
    return invalidRequestResponse(submission.message);
  }
  const videoId = youtubeVideoId(submission.value.youtubeUrl);
  if (videoId === null) {
    return errorResponse(422, "INPUT_NOT_YOUTUBE", "youtube_url is not a YouTube video URL");
  }
  const idempotencyKey = request.headers.get("Idempotency-Key");
  return respondWithAcceptedRun(ctx, submission.value, videoId, idempotencyKey);
});

export const readRun = httpAction(async (ctx, request) => {
  if (!(await isServiceCaller(request))) {
    return unauthorizedResponse();
  }
  const route = clientReadRoute(new URL(request.url).pathname);
  if (route === null) {
    return notFoundResponse();
  }
  return route.endpoint === "status"
    ? runStatusResponse(ctx, route.runId)
    : runResultResponse(ctx, route.runId);
});

async function respondWithAcceptedRun(
  ctx: ActionCtx,
  submission: SubmitRunRequest,
  videoId: string,
  idempotencyKey: string | null,
): Promise<Response> {
  const accepted = await ctx.runMutation(internal.runs.createRun, {
    video_id: videoId,
    youtube_url: canonicalWatchUrl(videoId),
    lang: submission.lang,
    ...(submission.externalRef === null ? {} : { external_ref: submission.externalRef }),
    ...(idempotencyKey === null || idempotencyKey === "" ? {} : { idempotency_key: idempotencyKey }),
  });
  return jsonResponse(202, { run_id: accepted.run_id, status: "queued", video_id: accepted.video_id });
}

async function runStatusResponse(ctx: ActionCtx, runId: string): Promise<Response> {
  const status = await ctx.runQuery(internal.runs.runStatus, { runId });
  return status === null ? runNotFoundResponse() : jsonResponse(200, status);
}

async function runResultResponse(ctx: ActionCtx, runId: string): Promise<Response> {
  const lookup = await ctx.runQuery(internal.runs.runResult, { runId });
  switch (lookup.kind) {
    case "not_found":
      return runNotFoundResponse();
    case "not_finished":
      return errorResponse(409, "RUN_NOT_FINISHED", "run has not succeeded");
    case "ready":
      return jsonResponse(200, resultBody(lookup.result));
  }
}

function runNotFoundResponse(): Response {
  return errorResponse(404, "RUN_NOT_FOUND", "run not found");
}
