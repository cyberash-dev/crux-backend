import { internal } from "./_generated/api";
import type { Doc } from "./_generated/dataModel";
import { type DatabaseReader, internalMutation, type MutationCtx } from "./_generated/server";
import { configuredMaxParallelRuns } from "./config/maxParallelRuns";
import { ACTIVE_RUN_STATUSES } from "./model/runVocabulary";

export const dispatch = internalMutation({
  args: {},
  handler: async (ctx): Promise<void> => {
    const maxParallelRuns = configuredMaxParallelRuns();
    let activeRunCount = await boundedActiveRunCount(ctx.db, maxParallelRuns);
    while (activeRunCount < maxParallelRuns) {
      const nextRun = await oldestQueuedRun(ctx.db);
      if (nextRun === null) {
        return;
      }
      await startProvisioning(ctx, nextRun);
      activeRunCount += 1;
    }
  },
});

async function boundedActiveRunCount(db: DatabaseReader, bound: number): Promise<number> {
  const activeRunsByStatus = await Promise.all(
    ACTIVE_RUN_STATUSES.map((status) =>
      db
        .query("runs")
        .withIndex("by_status_and_created_at", (q) => q.eq("status", status))
        .take(bound),
    ),
  );
  return activeRunsByStatus.reduce((count, runs) => count + runs.length, 0);
}

async function oldestQueuedRun(db: DatabaseReader): Promise<Doc<"runs"> | null> {
  return db
    .query("runs")
    .withIndex("by_status_and_created_at", (q) => q.eq("status", "queued"))
    .order("asc")
    .first();
}

async function startProvisioning(ctx: MutationCtx, run: Doc<"runs">): Promise<void> {
  const now = Date.now();
  await ctx.db.patch("runs", run._id, { status: "provisioning", last_event_at: now, updated_at: now });
  await ctx.scheduler.runAfter(0, internal.provisioning.provisionRun, { runId: run._id });
}
