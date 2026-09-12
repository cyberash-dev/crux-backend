import { cronJobs } from "convex/server";
import { internal } from "./_generated/api";

const crons = cronJobs();

crons.interval("fail silent runs", { minutes: 5 }, internal.watchdog.failSilentRuns, {});

export default crons;
