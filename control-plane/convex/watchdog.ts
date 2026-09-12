import { internalMutation } from "./_generated/server";
import { finishRun } from "./model/runLifecycle";
import { ACTIVE_RUN_STATUSES } from "./model/runVocabulary";

const WORKER_SILENCE_LIMIT_MS = 15 * 60 * 1000;

export const failSilentRuns = internalMutation({
  args: {},
  handler: async (ctx): Promise<void> => {
    const silentBefore = Date.now() - WORKER_SILENCE_LIMIT_MS;
    for (const status of ACTIVE_RUN_STATUSES) {
      const activeRuns = await ctx.db
        .query("runs")
        .withIndex("by_status_and_created_at", (q) => q.eq("status", status))
        .collect();
      for (const run of activeRuns.filter((activeRun) => activeRun.last_event_at < silentBefore)) {
        await finishRun(ctx, run, {
          status: "failed",
          error: { code: "WORKER_LOST", message: "no worker event for 15 minutes" },
        });
      }
    }
  },
});
