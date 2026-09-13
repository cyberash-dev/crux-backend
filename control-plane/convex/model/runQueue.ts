import type { Id } from "../_generated/dataModel";
import type { DatabaseReader } from "../_generated/server";
import { ACTIVE_RUN_STATUSES } from "./runVocabulary";

export async function queuedRunCountBefore(
  db: DatabaseReader,
  runId: Id<"runs">,
  createdAt: number,
): Promise<number> {
  const queuedRuns = await db
    .query("runs")
    .withIndex("by_status_and_created_at", (q) => q.eq("status", "queued").lte("created_at", createdAt))
    .collect();
  return queuedRuns.filter((queuedRun) => queuedRun._id !== runId).length;
}

export async function activeRunCount(db: DatabaseReader): Promise<number> {
  const activeRunsByStatus = await Promise.all(
    ACTIVE_RUN_STATUSES.map((status) =>
      db
        .query("runs")
        .withIndex("by_status_and_created_at", (q) => q.eq("status", status))
        .collect(),
    ),
  );
  return activeRunsByStatus.reduce((count, runs) => count + runs.length, 0);
}
