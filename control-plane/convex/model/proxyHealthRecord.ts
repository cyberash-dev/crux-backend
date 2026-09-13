import { internal } from "../_generated/api";
import type { Doc } from "../_generated/dataModel";
import type { DatabaseReader, DatabaseWriter, MutationCtx } from "../_generated/server";
import { configuredProxyUrls } from "../config/proxyUrls";
import { proxySummaryNotice } from "./proxyHealthNotices";
import type { KnownProxyHealthStatus, ProxyCheck } from "./proxyHealthVocabulary";

type ProxyHealth = Doc<"proxy_health">;
type ProxyHealthFields = Omit<ProxyHealth, "_id" | "_creationTime">;

/* Checks of indexes outside the current PROXY_URL list are dropped: the
   list may have changed since the probe or the run took its proxy. */
export async function recordProxyChecks(ctx: MutationCtx, checks: readonly ProxyCheck[]): Promise<void> {
  const now = Date.now();
  const proxyUrls = configuredProxyUrls();
  const blockedIndexesBefore = await blockedProxyIndexes(ctx.db, proxyUrls.length);
  for (const check of checks.filter((listedCheck) => listedCheck.proxy_index < proxyUrls.length)) {
    await storeProxyCheck(ctx.db, check, now);
  }
  const blockedIndexesAfter = await blockedProxyIndexes(ctx.db, proxyUrls.length);
  if (blockedIndexesAfter.join(",") === blockedIndexesBefore.join(",")) {
    return;
  }
  const blockedProxyUrls = proxyUrls.filter((_, proxyIndex) => blockedIndexesAfter.includes(proxyIndex));
  await ctx.scheduler.runAfter(0, internal.operatorNotices.sendTexts, {
    texts: [proxySummaryNotice(proxyUrls.length, blockedProxyUrls)],
  });
}

async function storeProxyCheck(db: DatabaseWriter, check: ProxyCheck, now: number): Promise<void> {
  const previous = await db
    .query("proxy_health")
    .withIndex("by_proxy_index", (q) => q.eq("proxy_index", check.proxy_index))
    .unique();
  const health = healthAfter(previous, check, now);
  if (previous === null) {
    await db.insert("proxy_health", health);
  } else {
    await db.replace("proxy_health", previous._id, health);
  }
}

function healthAfter(previous: ProxyHealth | null, check: ProxyCheck, now: number): ProxyHealthFields {
  const lastKnownStatus = check.status === "unknown" ? previous?.last_known_status : check.status;
  return {
    proxy_index: check.proxy_index,
    status: check.status,
    since: previous !== null && previous.status === check.status ? previous.since : now,
    checked_at: now,
    ...(lastKnownStatus === undefined ? {} : { last_known_status: lastKnownStatus }),
  };
}

async function blockedProxyIndexes(db: DatabaseReader, proxyCount: number): Promise<number[]> {
  const healths = await db.query("proxy_health").collect();
  return Array.from({ length: proxyCount }, (_, proxyIndex) => proxyIndex).filter(
    (proxyIndex) =>
      statusForChangeCheck(healths.find((health) => health.proxy_index === proxyIndex)) === "blocked",
  );
}

/* A proxy never seen ok or blocked counts as ok. */
function statusForChangeCheck(health: ProxyHealth | undefined): KnownProxyHealthStatus {
  return health?.last_known_status ?? "ok";
}
