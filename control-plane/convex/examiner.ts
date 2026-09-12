"use node";

import { v } from "convex/values";
import { internal } from "./_generated/api";
import type { Id } from "./_generated/dataModel";
import { type ActionCtx, internalAction } from "./_generated/server";
import { requiredEnv } from "./config/env";
import type { OpenedExam } from "./exams";
import type { ExaminerTurn } from "./model/examValidators";
import type { ExaminerGateway } from "./sandbox/examinerGateway";
import { daytonaExaminerGateway } from "./sandbox/examinerGatewayFactory";
import {
  type ExaminerLaunchConfig,
  examinerLaunchConfig,
  examinerSandboxSpec,
} from "./sandbox/examinerLaunch";
import { OPEN_TURN_INPUT } from "./sandbox/examinerTurnInput";
import { examinerTurnOutput } from "./sandbox/examinerTurnOutput";
import { SandboxCommandTimeoutError } from "./sandbox/sandboxCommandTimeoutError";
import { SandboxNotFoundError } from "./sandbox/sandboxNotFoundError";
import { redactedErrorMessage, redactedText } from "./security/secretRedaction";

export type TurnFailure = { kind: "failed" } | { kind: "timed_out" };

type ExamOpening = ({ kind: "opened" } & OpenedExam) | { kind: "failed" };

type TurnResult = { kind: "completed"; turn: ExaminerTurn } | TurnFailure;

type Examiner = { gateway: ExaminerGateway; config: ExaminerLaunchConfig };

type ExamOfRun = { examId: string; runId: Id<"runs"> };

type ReplyTurn = ExamOfRun & { sandboxId: string; turnInput: string };

class ExaminerExitError extends Error {
  constructor(
    readonly exitCode: number,
    readonly stderrTail: string,
  ) {
    super(`konspekt-exam-turn exited with ${exitCode}`);
    this.name = "ExaminerExitError";
  }
}

class InvalidTurnOutputError extends Error {
  constructor(reason: string) {
    super(`konspekt-exam-turn output is invalid: ${reason}`);
    this.name = "InvalidTurnOutputError";
  }
}

export const openExam = internalAction({
  args: { runId: v.id("runs") },
  handler: async (ctx, { runId }): Promise<ExamOpening> => {
    const examId = crypto.randomUUID();
    try {
      return { kind: "opened", ...(await openedExam(ctx, { examId, runId })) };
    } catch (error) {
      logTurnFailure(error, { exam_id: examId, run_id: runId });
      return { kind: "failed" };
    }
  },
});

export const replyTurn = internalAction({
  args: {
    examId: v.string(),
    runId: v.id("runs"),
    sandboxId: v.string(),
    turnInput: v.string(),
  },
  handler: async (ctx, reply): Promise<TurnResult> => {
    try {
      return { kind: "completed", turn: await repliedTurn(ctx, reply) };
    } catch (error) {
      logTurnFailure(error, { exam_id: reply.examId });
      return error instanceof SandboxCommandTimeoutError ? { kind: "timed_out" } : { kind: "failed" };
    }
  },
});

export const deleteSandbox = internalAction({
  args: { examId: v.string(), sandboxId: v.string() },
  handler: async (_ctx, { examId, sandboxId }): Promise<void> => {
    try {
      await daytonaExaminerGateway(requiredEnv("DAYTONA_API_KEY")).delete(sandboxId);
    } catch (error) {
      if (error instanceof SandboxNotFoundError) {
        return;
      }
      console.error("exam.sandbox_delete_failed", {
        exam_id: examId,
        sandbox_id: sandboxId,
        message: redactedErrorMessage(error),
      });
    }
  },
});

async function openedExam(ctx: ActionCtx, exam: ExamOfRun): Promise<OpenedExam> {
  const examiner = configuredExaminer();
  const sandboxId = await preparedSandbox(ctx, examiner, exam);
  try {
    const turn = await completedTurn(examiner.gateway, sandboxId, OPEN_TURN_INPUT);
    return await ctx.runMutation(internal.exams.createExam, {
      exam_id: exam.examId,
      run_id: exam.runId,
      sandbox_id: sandboxId,
      turn,
    });
  } catch (error) {
    await deleteQuietly(examiner.gateway, sandboxId, exam.examId);
    throw error;
  }
}

async function repliedTurn(ctx: ActionCtx, reply: ReplyTurn): Promise<ExaminerTurn> {
  const examiner = configuredExaminer();
  const turn = await turnInLiveSandbox(examiner.gateway, reply.sandboxId, reply.turnInput);
  if (turn !== null) {
    return turn;
  }
  const sandboxId = await preparedSandbox(ctx, examiner, reply);
  await ctx.runMutation(internal.examTurns.recordSandbox, { examId: reply.examId, sandboxId });
  return completedTurn(examiner.gateway, sandboxId, reply.turnInput);
}

async function turnInLiveSandbox(
  gateway: ExaminerGateway,
  sandboxId: string,
  turnInput: string,
): Promise<ExaminerTurn | null> {
  try {
    return await completedTurn(gateway, sandboxId, turnInput);
  } catch (error) {
    if (error instanceof SandboxNotFoundError) {
      return null;
    }
    throw error;
  }
}

async function preparedSandbox(ctx: ActionCtx, examiner: Examiner, exam: ExamOfRun): Promise<string> {
  const materials = await ctx.runQuery(internal.exams.examMaterials, { runId: exam.runId });
  const notes = await ctx.storage.get(materials.notes_storage_id);
  if (notes === null) {
    throw new Error(`konspekt.md of run ${exam.runId} is missing from storage`);
  }
  const sandboxId = await examiner.gateway.create(examinerSandboxSpec(examiner.config, exam.examId));
  try {
    await examiner.gateway.upload(sandboxId, {
      name: "konspekt.md",
      content: new Uint8Array(await notes.arrayBuffer()),
    });
    await examiner.gateway.upload(sandboxId, { name: "quiz.json", content: utf8(materials.quiz_json) });
    return sandboxId;
  } catch (error) {
    await deleteQuietly(examiner.gateway, sandboxId, exam.examId);
    throw error;
  }
}

async function completedTurn(
  gateway: ExaminerGateway,
  sandboxId: string,
  turnInput: string,
): Promise<ExaminerTurn> {
  await gateway.upload(sandboxId, { name: "turn.json", content: utf8(turnInput) });
  const result = await gateway.runTurn(sandboxId);
  if (result.exitCode !== 0) {
    throw new ExaminerExitError(result.exitCode, await stderrTail(gateway, sandboxId));
  }
  const output = examinerTurnOutput(result.stdout);
  if (output.kind === "invalid") {
    throw new InvalidTurnOutputError(output.message);
  }
  return output.value;
}

/* The tail only enriches the failure log; failing to read it must not
   replace the examiner's exit code as the reported cause. */
async function stderrTail(gateway: ExaminerGateway, sandboxId: string): Promise<string> {
  try {
    return await gateway.turnErrorTail(sandboxId);
  } catch (error) {
    return `turn.err unreadable: ${error instanceof Error ? error.message : String(error)}`;
  }
}

async function deleteQuietly(gateway: ExaminerGateway, sandboxId: string, examId: string): Promise<void> {
  try {
    await gateway.delete(sandboxId);
  } catch (error) {
    console.error("exam.sandbox_delete_failed", {
      exam_id: examId,
      sandbox_id: sandboxId,
      message: redactedErrorMessage(error),
    });
  }
}

function logTurnFailure(error: unknown, context: Readonly<Record<string, string>>): void {
  if (error instanceof SandboxCommandTimeoutError) {
    console.error("exam.turn_timed_out", context);
    return;
  }
  if (error instanceof ExaminerExitError) {
    console.error("exam.turn_failed", {
      ...context,
      exit_code: error.exitCode,
      stderr_tail: redactedText(error.stderrTail),
    });
    return;
  }
  console.error("exam.turn_failed", { ...context, message: redactedErrorMessage(error) });
}

function configuredExaminer(): Examiner {
  const config = examinerLaunchConfig();
  return { config, gateway: daytonaExaminerGateway(config.daytonaApiKey) };
}

function utf8(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}
