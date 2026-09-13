import { cronJobs } from "convex/server";
import { internal } from "./_generated/api";

const crons = cronJobs();

crons.interval("fail silent runs", { minutes: 5 }, internal.watchdog.failSilentRuns, {});
crons.interval("probe proxies", { hours: 1 }, internal.proxyProbe.probeProxies, {});

export default crons;
