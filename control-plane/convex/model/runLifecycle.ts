import { internal } from "../_generated/api";
import type { Doc } from "../_generated/dataModel";
import type { DatabaseReader, MutationCtx } from "../_generated/server";
import { runFailedNotice, runSucceededNotice } from "./runNotices";

export type TerminalOutcome =
  | { status: "succeeded"; llm_spend_usd?: number }
  | { status: "failed"; error: { code: string; message: string } };

/* Every terminal status is set here, so every finished run sends exactly
   one operator message. */
export async function finishRun(
  ctx: MutationCtx,
  run: Doc<"runs">,
  outcome: TerminalOutcome,
): Promise<void> {
  const now = Date.now();
  await ctx.db.patch("runs", run._id, { ...outcome, updated_at: now });
  await deleteRunSandbox(ctx, run);
  await ctx.scheduler.runAfter(0, internal.dispatcher.dispatch, {});
  await ctx.scheduler.runAfter(0, internal.operatorNotices.sendTexts, {
    texts: [await runFinishedNotice(ctx.db, run, outcome, now)],
  });
}

/* The run stays provisioning, so it keeps its slot among the active runs.
   Clearing the token hash revokes the old worker's token and lets the next
   provisioning action claim the run with a fresh one. */
export async function provisionRunAgain(
  ctx: MutationCtx,
  run: Doc<"runs">,
  blockedProxyIndexes: readonly number[],
): Promise<void> {
  const now = Date.now();
  await ctx.db.patch("runs", run._id, {
    status: "provisioning",
    token_hash: undefined,
    sandbox_id: undefined,
    proxy_index: undefined,
    blocked_proxy_indexes: [...blockedProxyIndexes],
    last_event_at: now,
    updated_at: now,
  });
  await deleteRunSandbox(ctx, run);
  await ctx.scheduler.runAfter(0, internal.provisioning.provisionRun, { runId: run._id });
}

async function deleteRunSandbox(ctx: MutationCtx, run: Doc<"runs">): Promise<void> {
  if (run.sandbox_id !== undefined) {
    await ctx.scheduler.runAfter(0, internal.provisioning.deleteSandbox, {
      runId: run._id,
      sandboxId: run.sandbox_id,
    });
  }
}

async function runFinishedNotice(
  db: DatabaseReader,
  run: Doc<"runs">,
  outcome: TerminalOutcome,
  finishedAt: number,
): Promise<string> {
  if (outcome.status === "failed") {
    return runFailedNotice(run, outcome.error, finishedAt);
  }
  const result = await db
    .query("run_results")
    .withIndex("by_run_id", (q) => q.eq("run_id", run._id))
    .first();
  if (result === null) {
    throw new Error(`succeeded run ${run._id} has no stored result`);
  }
  return runSucceededNotice(run, result.video.title, finishedAt);
}
