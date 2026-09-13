"use node";

import { v } from "convex/values";
import { internal } from "./_generated/api";
import { type ActionCtx, internalAction } from "./_generated/server";
import { requiredEnv } from "./config/env";
import { daytonaSandboxGateway } from "./sandbox/daytonaGatewayFactory";
import { sandboxSpec, type WorkerLaunch, workerLaunchConfig } from "./sandbox/workerLaunch";
import { newRunToken } from "./security/runToken";
import { redactedErrorMessage } from "./security/secretRedaction";
import { sha256Hex } from "./security/sha256";

export const provisionRun = internalAction({
  args: { runId: v.id("runs") },
  handler: async (ctx, { runId }): Promise<void> => {
    const runToken = newRunToken();
    const claim = await ctx.runMutation(internal.sandboxRuns.claimProvisioning, {
      runId,
      tokenHash: await sha256Hex(runToken),
    });
    if (claim === null) {
      return;
    }
    try {
      await launchWorker(ctx, {
        runId,
        runToken,
        youtubeUrl: claim.youtube_url,
        lang: claim.lang,
        proxyIndex: claim.proxy_index,
      });
    } catch (error) {
      const message = redactedErrorMessage(error, [runToken]);
      console.error("sandbox.start_failed", { run_id: runId, message });
      await ctx.runMutation(internal.sandboxRuns.failProvisioning, { runId, message });
    }
  },
});

export const deleteSandbox = internalAction({
  args: { runId: v.id("runs"), sandboxId: v.string() },
  handler: async (_ctx, { runId, sandboxId }): Promise<void> => {
    try {
      await daytonaSandboxGateway(requiredEnv("DAYTONA_API_KEY")).delete(sandboxId);
    } catch (error) {
      console.error("sandbox.delete_failed", {
        run_id: runId,
        sandbox_id: sandboxId,
        message: redactedErrorMessage(error),
      });
    }
  },
});

async function launchWorker(ctx: ActionCtx, launch: WorkerLaunch): Promise<void> {
  const config = workerLaunchConfig();
  const gateway = daytonaSandboxGateway(config.daytonaApiKey);
  const sandboxId = await gateway.create(sandboxSpec(config, launch));
  await ctx.runMutation(internal.sandboxRuns.recordSandbox, { runId: launch.runId, sandboxId });
  await gateway.startWorker(sandboxId);
}
