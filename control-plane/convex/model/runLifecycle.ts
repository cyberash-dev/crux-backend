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
  if (run.sandbox_id !== undefined) {
    await ctx.scheduler.runAfter(0, internal.provisioning.deleteSandbox, {
      runId: run._id,
      sandboxId: run.sandbox_id,
    });
  }
  await ctx.scheduler.runAfter(0, internal.dispatcher.dispatch, {});
}
