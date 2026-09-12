import type { Doc } from "../_generated/dataModel";
import type { DatabaseReader } from "../_generated/server";
import { runByIdText } from "./runLookup";
import { isTerminalStatus } from "./runVocabulary";

export type WorkerAccess =
  | { kind: "granted"; run: Doc<"runs"> }
  | { kind: "unauthorized" }
  | { kind: "terminal" };

export async function workerAccess(
  db: DatabaseReader,
  runId: string,
  tokenHash: string,
): Promise<WorkerAccess> {
  const run = await runByIdText(db, runId);
  if (run === null || run.token_hash !== tokenHash) {
    return { kind: "unauthorized" };
  }
  return isTerminalStatus(run.status) ? { kind: "terminal" } : { kind: "granted", run };
}
