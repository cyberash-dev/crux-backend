const DEFAULT_MAX_PARALLEL_RUNS = 1;
const POSITIVE_INTEGER = /^[1-9][0-9]*$/;

export function configuredMaxParallelRuns(): number {
  const configured = process.env.MAX_PARALLEL_RUNS;
  if (configured === undefined || configured === "") {
    return DEFAULT_MAX_PARALLEL_RUNS;
  }
  if (!POSITIVE_INTEGER.test(configured)) {
    throw new Error("MAX_PARALLEL_RUNS must be a positive integer");
  }
  return Number(configured);
}
