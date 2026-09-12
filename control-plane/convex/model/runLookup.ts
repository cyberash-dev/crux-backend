import type { Doc, Id } from "../_generated/dataModel";
import type { DatabaseReader } from "../_generated/server";

export async function runByIdText(db: DatabaseReader, runId: string): Promise<Doc<"runs"> | null> {
  const id = db.normalizeId("runs", runId);
  return id === null ? null : db.get("runs", id);
}

export async function existingRun(db: DatabaseReader, runId: Id<"runs">): Promise<Doc<"runs">> {
  const run = await db.get("runs", runId);
  if (run === null) {
    throw new Error(`run ${runId} does not exist`);
  }
  return run;
}
