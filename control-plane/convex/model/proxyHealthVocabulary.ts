import { v } from "convex/values";

export const PROXY_HEALTH_STATUSES = ["ok", "blocked", "unknown"] as const;
export type ProxyHealthStatus = (typeof PROXY_HEALTH_STATUSES)[number];
export type KnownProxyHealthStatus = Exclude<ProxyHealthStatus, "unknown">;

export const proxyHealthStatusValidator = v.union(
  ...PROXY_HEALTH_STATUSES.map((status) => v.literal(status)),
);

export const knownProxyHealthStatusValidator = v.union(v.literal("ok"), v.literal("blocked"));

export const proxyCheckValidator = v.object({
  proxy_index: v.number(),
  status: proxyHealthStatusValidator,
});

export type ProxyCheck = { proxy_index: number; status: ProxyHealthStatus };
