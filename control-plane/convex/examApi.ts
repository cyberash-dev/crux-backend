import { internal } from "./_generated/api";
import type { Id } from "./_generated/dataModel";
import { type ActionCtx, httpAction } from "./_generated/server";
import type { TurnFailure } from "./examiner";
import type { ClaimedTurn } from "./examTurns";
import { examMessageRequest } from "./httpBoundary/examMessageRequest";
import { jsonBody } from "./httpBoundary/jsonBody";
import {
  errorResponse,
  invalidRequestResponse,
  jsonResponse,
  notFoundResponse,
  unauthorizedResponse,
} from "./httpBoundary/responses";
import { examOpenRunId, examRoute } from "./httpBoundary/routes";
import { isServiceCaller } from "./httpBoundary/serviceAuth";
import { replyTurnInput } from "./sandbox/examinerTurnInput";

export const openExam = httpAction(async (ctx, request) => {
  if (!(await isServiceCaller(request))) {
    return unauthorizedResponse();
  }
  const runId = examOpenRunId(new URL(request.url).pathname);
  if (runId === null) {
    return notFoundResponse();
  }
  const run = await ctx.runQuery(internal.exams.openableRun, { runId });
  switch (run.kind) {
    case "not_found":
      return errorResponse(404, "RUN_NOT_FOUND", "run not found");
    case "not_finished":
      return errorResponse(409, "RUN_NOT_FINISHED", "run has not succeeded");
    case "openable":
      return openedExamResponse(ctx, run.run_id);
  }
});

export const readExam = httpAction(async (ctx, request) => {
  if (!(await isServiceCaller(request))) {
    return unauthorizedResponse();
  }
  const route = examRoute(new URL(request.url).pathname);
  if (route === null || route.endpoint === "close") {
    return notFoundResponse();
  }
  return route.endpoint === "exam"
    ? examStatusResponse(ctx, route.examId)
    : examMessagesResponse(ctx, route.examId);
});

export const writeExam = httpAction(async (ctx, request) => {
  if (!(await isServiceCaller(request))) {
    return unauthorizedResponse();
  }
  const route = examRoute(new URL(request.url).pathname);
  if (route === null || route.endpoint === "exam") {
    return notFoundResponse();
  }
  return route.endpoint === "close"
    ? closedExamResponse(ctx, route.examId)
    : studentMessageResponse(ctx, route.examId, request);
});

async function openedExamResponse(ctx: ActionCtx, runId: Id<"runs">): Promise<Response> {
  const opening = await ctx.runAction(internal.examiner.openExam, { runId });
  if (opening.kind !== "opened") {
    return examinerFailureResponse(opening);
  }
  return jsonResponse(201, {
    exam_id: opening.exam_id,
    run_id: opening.run_id,
    status: opening.status,
    progress: opening.progress,
    examiner_message: opening.examiner_message,
  });
}

async function examStatusResponse(ctx: ActionCtx, examId: string): Promise<Response> {
  const exam = await ctx.runQuery(internal.exams.examStatus, { examId });
  return exam === null ? examNotFoundResponse() : jsonResponse(200, exam);
}

async function examMessagesResponse(ctx: ActionCtx, examId: string): Promise<Response> {
  const messages = await ctx.runQuery(internal.exams.examMessageList, { examId });
  return messages === null ? examNotFoundResponse() : jsonResponse(200, { messages });
}

async function closedExamResponse(ctx: ActionCtx, examId: string): Promise<Response> {
  const exam = await ctx.runMutation(internal.exams.closeExam, { examId });
  return exam === null ? examNotFoundResponse() : jsonResponse(200, exam);
}

async function studentMessageResponse(ctx: ActionCtx, examId: string, request: Request): Promise<Response> {
  const body = await jsonBody(request);
  if (body.kind === "malformed") {
    return invalidRequestResponse("body is not valid JSON");
  }
  const message = examMessageRequest(body.value);
  if (message.kind === "invalid") {
    return invalidRequestResponse(message.message);
  }
  const claim = await ctx.runMutation(internal.examTurns.claimTurn, { examId });
  switch (claim.kind) {
    case "not_found":
      return examNotFoundResponse();
    case "finished":
      return examFinishedResponse();
    case "in_progress":
      return turnInProgressResponse();
    case "claimed":
      return answeredTurnResponse(ctx, { examId, claim, studentText: message.value.text });
  }
}

async function answeredTurnResponse(
  ctx: ActionCtx,
  turn: { examId: string; claim: ClaimedTurn; studentText: string },
): Promise<Response> {
  const { examId, claim, studentText } = turn;
  const result = await ctx.runAction(internal.examiner.replyTurn, {
    examId,
    runId: claim.run_id,
    sandboxId: claim.sandbox_id,
    turnInput: replyTurnInput(claim.state_json, claim.messages, studentText),
  });
  if (result.kind !== "completed") {
    await ctx.runMutation(internal.examTurns.releaseTurn, { examId, claimedAt: claim.claimed_at });
    return examinerFailureResponse(result);
  }
  const stored = await ctx.runMutation(internal.examTurns.completeTurn, {
    examId,
    claimedAt: claim.claimed_at,
    studentText,
    turn: result.turn,
  });
  switch (stored.kind) {
    case "finished":
      return examFinishedResponse();
    case "claim_lost":
      return turnInProgressResponse();
    case "stored":
      return jsonResponse(200, {
        status: stored.status,
        progress: stored.progress,
        student_message: stored.student_message,
        examiner_message: stored.examiner_message,
      });
  }
}

/* The Convex edge replaces 502 and 504 bodies with its own page, so both
   examiner errors answer 503 and stay apart through their code. */
function examinerFailureResponse(failure: TurnFailure): Response {
  return failure.kind === "timed_out"
    ? errorResponse(503, "EXAMINER_TIMEOUT", "the examiner did not answer within 120 s; nothing was stored")
    : errorResponse(503, "EXAMINER_FAILED", "the examiner failed; nothing was stored");
}

function examNotFoundResponse(): Response {
  return errorResponse(404, "EXAM_NOT_FOUND", "exam not found");
}

function examFinishedResponse(): Response {
  return errorResponse(409, "EXAM_FINISHED", "exam is mastered or closed");
}

function turnInProgressResponse(): Response {
  return errorResponse(409, "EXAM_TURN_IN_PROGRESS", "another student message of the exam is being answered");
}
