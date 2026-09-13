import { internal } from "../_generated/api";
import type { Doc } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

export type TerminalOutcome =
  | { status: "succeeded"; llm_spend_usd?: number }
  | { status: "failed"; error: { code: string; message: string } };

export async function finishRun(
  ctx: MutationCtx,
  run: Doc<"runs">,
  outcome: TerminalOutcome,
): Promise<void> {
  await ctx.db.patch("runs", run._id, { ...outcome, updated_at: Date.now() });
  await deleteRunSandbox(ctx, run);
  await ctx.scheduler.runAfter(0, internal.dispatcher.dispatch, {});
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
