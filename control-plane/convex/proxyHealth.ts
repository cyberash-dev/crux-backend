import { v } from "convex/values";
import { internalMutation } from "./_generated/server";
import { recordProxyChecks } from "./model/proxyHealthRecord";
import { proxyCheckValidator } from "./model/proxyHealthVocabulary";

export const recordProbeChecks = internalMutation({
  args: { checks: v.array(proxyCheckValidator) },
  handler: async (ctx, { checks }): Promise<void> => {
    await recordProxyChecks(ctx, checks);
  },
});
