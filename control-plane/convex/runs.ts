import { v } from "convex/values";
import { internal } from "./_generated/api";
import type { Id } from "./_generated/dataModel";
import { internalMutation, internalQuery } from "./_generated/server";
import { runByIdText } from "./model/runLookup";
import { activeRunCount, queuedRunCountBefore } from "./model/runQueue";
import { runStatusView, type RunStatusView } from "./model/runStatusView";
import { runLangValidator } from "./model/runValidators";
import { type StoredRunResult, storedRunResult } from "./model/storedRunResult";

type AcceptedRun = { run_id: Id<"runs">; video_id: string };

type RunResultLookup =
  | { kind: "not_found" }
  | { kind: "not_finished" }
  | { kind: "ready"; result: StoredRunResult };

export const createRun = internalMutation({
  args: {
    video_id: v.string(),
    youtube_url: v.string(),
    lang: runLangValidator,
    external_ref: v.optional(v.string()),
    idempotency_key: v.optional(v.string()),
  },
  handler: async (ctx, args): Promise<AcceptedRun> => {
    const { idempotency_key: idempotencyKey } = args;
    if (idempotencyKey !== undefined) {
      const firstRun = await ctx.db
        .query("runs")
        .withIndex("by_idempotency_key", (q) => q.eq("idempotency_key", idempotencyKey))
        .first();
      if (firstRun !== null) {
        return { run_id: firstRun._id, video_id: firstRun.video_id };
      }
    }
    const now = Date.now();
    const runId = await ctx.db.insert("runs", {
      ...args,
      status: "queued",
      stages: [],
      last_event_at: now,
      created_at: now,
      updated_at: now,
    });
    await ctx.scheduler.runAfter(0, internal.dispatcher.dispatch, {});
    await ctx.scheduler.runAfter(0, internal.operatorNotices.sendRunSubmitted, {
      run_id: runId,
      youtube_url: args.youtube_url,
      ...(args.external_ref === undefined ? {} : { external_ref: args.external_ref }),
      queued_ahead: await queuedRunCountBefore(ctx.db, runId, now),
      active_runs: await activeRunCount(ctx.db),
    });
    return { run_id: runId, video_id: args.video_id };
  },
});

export const runStatus = internalQuery({
  args: { runId: v.string() },
  handler: async (ctx, { runId }): Promise<RunStatusView | null> => {
    const run = await runByIdText(ctx.db, runId);
    return run === null ? null : runStatusView(run);
  },
});

export const runResult = internalQuery({
  args: { runId: v.string() },
  handler: async (ctx, { runId }): Promise<RunResultLookup> => {
    const run = await runByIdText(ctx.db, runId);
    if (run === null) {
      return { kind: "not_found" };
    }
    if (run.status !== "succeeded") {
      return { kind: "not_finished" };
    }
    return { kind: "ready", result: await storedRunResult(ctx, run) };
  },
});
