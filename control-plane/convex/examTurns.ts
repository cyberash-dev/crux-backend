import { v } from "convex/values";
import { internal } from "./_generated/api";
import type { Id } from "./_generated/dataModel";
import { internalMutation } from "./_generated/server";
import { examByExamId, examMessages, existingExam, lastMessageSeq } from "./model/examLookup";
import { type ExamMessage, examMessageView, type ExamMessageView } from "./model/examMessageView";
import { examinerTurnValidator, type ExamProgress } from "./model/examValidators";
import type { ExamStatus } from "./model/examVocabulary";
import type { TranscriptMessage } from "./sandbox/examinerTurnInput";

const TURN_CLAIM_LIFETIME_MS = 3 * 60 * 1000;

export type ClaimedTurn = {
  kind: "claimed";
  claimed_at: number;
  run_id: Id<"runs">;
  sandbox_id: string;
  state_json: string;
  messages: TranscriptMessage[];
};

type TurnClaim = { kind: "not_found" } | { kind: "finished" } | { kind: "in_progress" } | ClaimedTurn;

type StoredTurn =
  | { kind: "finished" }
  | { kind: "claim_lost" }
  | {
      kind: "stored";
      status: ExamStatus;
      progress: ExamProgress;
      student_message: ExamMessageView;
      examiner_message: ExamMessageView;
    };

export const claimTurn = internalMutation({
  args: { examId: v.string() },
  handler: async (ctx, { examId }): Promise<TurnClaim> => {
    const exam = await examByExamId(ctx.db, examId);
    if (exam === null) {
      return { kind: "not_found" };
    }
    if (exam.status !== "active") {
      return { kind: "finished" };
    }
    const now = Date.now();
    if (exam.turn_claimed_at !== undefined && now - exam.turn_claimed_at <= TURN_CLAIM_LIFETIME_MS) {
      return { kind: "in_progress" };
    }
    await ctx.db.patch("exams", exam._id, { turn_claimed_at: now });
    const messages = await examMessages(ctx.db, examId);
    return {
      kind: "claimed",
      claimed_at: now,
      run_id: exam.run_id,
      sandbox_id: exam.sandbox_id,
      state_json: exam.state_json,
      messages: messages.map(({ role, text }) => ({ role, text })),
    };
  },
});

export const releaseTurn = internalMutation({
  args: { examId: v.string(), claimedAt: v.number() },
  handler: async (ctx, { examId, claimedAt }): Promise<void> => {
    const exam = await existingExam(ctx.db, examId);
    if (exam.turn_claimed_at === claimedAt) {
      await ctx.db.patch("exams", exam._id, { turn_claimed_at: undefined });
    }
  },
});

export const recordSandbox = internalMutation({
  args: { examId: v.string(), sandboxId: v.string() },
  handler: async (ctx, { examId, sandboxId }): Promise<void> => {
    const exam = await existingExam(ctx.db, examId);
    await ctx.db.patch("exams", exam._id, { sandbox_id: sandboxId });
    if (exam.status !== "active") {
      await ctx.scheduler.runAfter(0, internal.examiner.deleteSandbox, { examId, sandboxId });
    }
  },
});

export const completeTurn = internalMutation({
  args: {
    examId: v.string(),
    claimedAt: v.number(),
    studentText: v.string(),
    turn: examinerTurnValidator,
  },
  handler: async (ctx, { examId, claimedAt, studentText, turn }): Promise<StoredTurn> => {
    const exam = await existingExam(ctx.db, examId);
    if (exam.status !== "active") {
      return { kind: "finished" };
    }
    if (exam.turn_claimed_at !== claimedAt) {
      return { kind: "claim_lost" };
    }
    const lastSeq = await lastMessageSeq(ctx.db, examId);
    const now = Date.now();
    const studentMessage: ExamMessage = {
      exam_id: examId,
      seq: lastSeq + 1,
      role: "student",
      text: studentText,
      created_at: now,
      ...(turn.graded === null ? {} : { question_id: turn.graded.question_id, verdict: turn.graded.verdict }),
    };
    const examinerMessage: ExamMessage = {
      exam_id: examId,
      seq: lastSeq + 2,
      role: "examiner",
      text: turn.examiner_message,
      created_at: now,
    };
    await ctx.db.insert("exam_messages", studentMessage);
    await ctx.db.insert("exam_messages", examinerMessage);
    const status = turn.is_mastered ? "mastered" : "active";
    await ctx.db.patch("exams", exam._id, {
      status,
      state_json: turn.state_json,
      progress: turn.progress,
      turn_claimed_at: undefined,
      updated_at: now,
    });
    if (turn.is_mastered) {
      await ctx.scheduler.runAfter(0, internal.examiner.deleteSandbox, {
        examId,
        sandboxId: exam.sandbox_id,
      });
    }
    return {
      kind: "stored",
      status,
      progress: turn.progress,
      student_message: examMessageView(studentMessage),
      examiner_message: examMessageView(examinerMessage),
    };
  },
});
