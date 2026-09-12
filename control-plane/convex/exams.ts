import { v } from "convex/values";
import { internal } from "./_generated/api";
import type { Id } from "./_generated/dataModel";
import { internalMutation, internalQuery } from "./_generated/server";
import { examByExamId, examMessages } from "./model/examLookup";
import { type ExamMessage, examMessageView, type ExamMessageView } from "./model/examMessageView";
import { examinerTurnValidator, type ExamProgress } from "./model/examValidators";
import { examView, type ExamView } from "./model/examView";
import type { ExamStatus } from "./model/examVocabulary";
import { runByIdText } from "./model/runLookup";

const NOTES_FILE_NAME = "konspekt.md";

type OpenableRun =
  | { kind: "not_found" }
  | { kind: "not_finished" }
  | { kind: "openable"; run_id: Id<"runs"> };

type ExamMaterials = { quiz_json: string; notes_storage_id: Id<"_storage"> };

export type OpenedExam = {
  exam_id: string;
  run_id: Id<"runs">;
  status: "active";
  progress: ExamProgress;
  examiner_message: ExamMessageView;
};

type ClosedExam = { exam_id: string; status: ExamStatus };

export const openableRun = internalQuery({
  args: { runId: v.string() },
  handler: async (ctx, { runId }): Promise<OpenableRun> => {
    const run = await runByIdText(ctx.db, runId);
    if (run === null) {
      return { kind: "not_found" };
    }
    return run.status === "succeeded" ? { kind: "openable", run_id: run._id } : { kind: "not_finished" };
  },
});

export const examMaterials = internalQuery({
  args: { runId: v.id("runs") },
  handler: async (ctx, { runId }): Promise<ExamMaterials> => {
    const result = await ctx.db
      .query("run_results")
      .withIndex("by_run_id", (q) => q.eq("run_id", runId))
      .unique();
    const files = await ctx.db
      .query("run_files")
      .withIndex("by_run_id", (q) => q.eq("run_id", runId))
      .collect();
    const notes = files.find((file) => file.kind === "markdown" && file.name === NOTES_FILE_NAME);
    if (result === null || notes === undefined) {
      throw new Error(`run ${runId} has no quiz or no ${NOTES_FILE_NAME}`);
    }
    return { quiz_json: result.quiz_json, notes_storage_id: notes.storage_id };
  },
});

export const createExam = internalMutation({
  args: {
    exam_id: v.string(),
    run_id: v.id("runs"),
    sandbox_id: v.string(),
    turn: examinerTurnValidator,
  },
  handler: async (ctx, { turn, ...exam }): Promise<OpenedExam> => {
    const now = Date.now();
    await ctx.db.insert("exams", {
      ...exam,
      status: "active",
      state_json: turn.state_json,
      progress: turn.progress,
      created_at: now,
      updated_at: now,
    });
    const examinerMessage: ExamMessage = {
      exam_id: exam.exam_id,
      seq: 1,
      role: "examiner",
      text: turn.examiner_message,
      created_at: now,
    };
    await ctx.db.insert("exam_messages", examinerMessage);
    return {
      exam_id: exam.exam_id,
      run_id: exam.run_id,
      status: "active",
      progress: turn.progress,
      examiner_message: examMessageView(examinerMessage),
    };
  },
});

export const examStatus = internalQuery({
  args: { examId: v.string() },
  handler: async (ctx, { examId }): Promise<ExamView | null> => {
    const exam = await examByExamId(ctx.db, examId);
    return exam === null ? null : examView(exam);
  },
});

export const examMessageList = internalQuery({
  args: { examId: v.string() },
  handler: async (ctx, { examId }): Promise<ExamMessageView[] | null> => {
    const exam = await examByExamId(ctx.db, examId);
    return exam === null ? null : (await examMessages(ctx.db, examId)).map(examMessageView);
  },
});

export const closeExam = internalMutation({
  args: { examId: v.string() },
  handler: async (ctx, { examId }): Promise<ClosedExam | null> => {
    const exam = await examByExamId(ctx.db, examId);
    if (exam === null) {
      return null;
    }
    if (exam.status !== "active") {
      return { exam_id: examId, status: exam.status };
    }
    await ctx.db.patch("exams", exam._id, { status: "closed", updated_at: Date.now() });
    await ctx.scheduler.runAfter(0, internal.examiner.deleteSandbox, {
      examId,
      sandboxId: exam.sandbox_id,
    });
    return { exam_id: examId, status: "closed" };
  },
});
