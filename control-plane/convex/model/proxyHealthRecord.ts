import { internal } from "../_generated/api";
import type { Doc } from "../_generated/dataModel";
import type { DatabaseReader, DatabaseWriter, MutationCtx } from "../_generated/server";
import { configuredProxyUrls } from "../config/proxyUrls";
import { everyProxyBlockedNotice, proxyStatusNotice } from "./proxyHealthNotices";
import type { KnownProxyHealthStatus, ProxyCheck } from "./proxyHealthVocabulary";

type ProxyHealth = Doc<"proxy_health">;
type ProxyHealthFields = Omit<ProxyHealth, "_id" | "_creationTime">;

/* Checks of indexes outside the current PROXY_URL list are dropped: the
   list may have changed since the probe or the run took its proxy. */
export async function recordProxyChecks(ctx: MutationCtx, checks: readonly ProxyCheck[]): Promise<void> {
  const now = Date.now();
  const proxyUrls = configuredProxyUrls();
  const notices: string[] = [];
  let hasProxyTurnedBlocked = false;
  for (const check of checks) {
    const proxyUrl = proxyUrls[check.proxy_index];
    if (proxyUrl === undefined) {
      continue;
    }
    const change = await storedStatusChange(ctx.db, check, now);
    if (change !== null) {
      const position = { proxyIndex: check.proxy_index, proxyCount: proxyUrls.length, proxyUrl };
      notices.push(proxyStatusNotice(position, change, now));
      hasProxyTurnedBlocked ||= change === "blocked";
    }
  }
  if (hasProxyTurnedBlocked && !(await hasOkProxy(ctx.db, proxyUrls.length))) {
    notices.push(everyProxyBlockedNotice(proxyUrls.length));
  }
  if (notices.length > 0) {
    await ctx.scheduler.runAfter(0, internal.proxyHealth.sendNotices, { texts: notices });
  }
}

async function storedStatusChange(
  db: DatabaseWriter,
  check: ProxyCheck,
  now: number,
): Promise<KnownProxyHealthStatus | null> {
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
  return check.status !== "unknown" && check.status !== statusForChangeCheck(previous) ? check.status : null;
}

/* A proxy never seen ok or blocked is presumed ok, so its first blocked
   check is reported as a change and its first ok check is not. */
function statusForChangeCheck(health: ProxyHealth | null | undefined): KnownProxyHealthStatus {
  return health?.last_known_status ?? "ok";
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

async function hasOkProxy(db: DatabaseReader, proxyCount: number): Promise<boolean> {
  const healths = await db.query("proxy_health").collect();
  return Array.from({ length: proxyCount }, (_, proxyIndex) => proxyIndex).some(
    (proxyIndex) =>
      statusForChangeCheck(healths.find((health) => health.proxy_index === proxyIndex)) === "ok",
  );
}
