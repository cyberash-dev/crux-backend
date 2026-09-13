"use node";

import { internal } from "./_generated/api";
import { internalAction } from "./_generated/server";
import { configuredProxyUrls } from "./config/proxyUrls";
import type { ProxyCheck } from "./model/proxyHealthVocabulary";
import { proxiedWatchPageClient } from "./watchPage/watchPageClientFactory";
import { probedWatchPage } from "./watchPage/watchPageProbe";

/* Scheduled hourly by crons.ts; `npx convex run proxyProbe:probeProxies`
   runs it on demand. */
export const probeProxies = internalAction({
  args: {},
  handler: async (ctx): Promise<void> => {
    const checks = await Promise.all(configuredProxyUrls().map(proxyCheck));
    await ctx.runMutation(internal.proxyHealth.recordProbeChecks, { checks });
  },
});

async function proxyCheck(proxyUrl: string, proxyIndex: number): Promise<ProxyCheck> {
  const probe = await probedWatchPage(proxiedWatchPageClient(proxyUrl));
  if (probe.status === "unknown") {
    console.warn("proxy_probe.unknown", { proxy_index: proxyIndex, detail: probe.detail });
  }
  return { proxy_index: proxyIndex, status: probe.status };
}
