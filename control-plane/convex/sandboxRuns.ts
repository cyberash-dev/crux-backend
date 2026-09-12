import { v } from "convex/values";
import { internal } from "./_generated/api";
import { internalMutation } from "./_generated/server";
import { finishRun } from "./model/runLifecycle";
import { existingRun } from "./model/runLookup";
import { isTerminalStatus, type RunLang } from "./model/runVocabulary";

export type ProvisioningClaim = { youtube_url: string; lang: RunLang };

/* The token hash is written at most once, so a repeated provisioning action
   for the same run gets no claim and starts no second sandbox. */
export const claimProvisioning = internalMutation({
  args: { runId: v.id("runs"), tokenHash: v.string() },
  handler: async (ctx, { runId, tokenHash }): Promise<ProvisioningClaim | null> => {
    const run = await existingRun(ctx.db, runId);
    if (run.status !== "provisioning" || run.token_hash !== undefined) {
      return null;
    }
    await ctx.db.patch("runs", runId, { token_hash: tokenHash, updated_at: Date.now() });
    return { youtube_url: run.youtube_url, lang: run.lang };
  },
});

export const recordSandbox = internalMutation({
  args: { runId: v.id("runs"), sandboxId: v.string() },
  handler: async (ctx, { runId, sandboxId }): Promise<void> => {
    const run = await existingRun(ctx.db, runId);
    await ctx.db.patch("runs", runId, { sandbox_id: sandboxId, updated_at: Date.now() });
    if (isTerminalStatus(run.status)) {
      await ctx.scheduler.runAfter(0, internal.provisioning.deleteSandbox, { runId, sandboxId });
    }
  },
});

export const failProvisioning = internalMutation({
  args: { runId: v.id("runs"), message: v.string() },
  handler: async (ctx, { runId, message }): Promise<void> => {
    const run = await existingRun(ctx.db, runId);
    if (isTerminalStatus(run.status)) {
      return;
    }
    await finishRun(ctx, run, { status: "failed", error: { code: "SANDBOX_START_FAILED", message } });
  },
});
