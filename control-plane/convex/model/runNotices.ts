import type { Doc } from "../_generated/dataModel";
import { redactedText } from "../security/secretRedaction";

export type SubmittedRun = {
  run_id: string;
  youtube_url: string;
  external_ref?: string;
  queued_ahead: number;
  active_runs: number;
};

const ERROR_MESSAGE_LIMIT = 200;
const MINUTE_MS = 60 * 1000;

export function runSubmittedNotice(run: SubmittedRun, maxParallelRuns: number): string {
  const reference = run.external_ref === undefined ? "" : ` (ref: ${run.external_ref})`;
  return (
    `New run ${run.run_id}: ${run.youtube_url}${reference}. ` +
    `Queued ahead: ${run.queued_ahead}. Active: ${run.active_runs}/${maxParallelRuns}.`
  );
}

export function runSucceededNotice(run: Doc<"runs">, videoTitle: string, finishedAt: number): string {
  return `Run ${run._id} succeeded in ${minutesSince(run, finishedAt)} min: ${videoTitle} ${run.youtube_url}`;
}

/* Redaction comes before the cut, so a cut can never leave part of a
   secret that redaction no longer recognises. */
export function runFailedNotice(
  run: Doc<"runs">,
  error: { code: string; message: string },
  finishedAt: number,
): string {
  const message = redactedText(error.message).slice(0, ERROR_MESSAGE_LIMIT);
  return `Run ${run._id} failed after ${minutesSince(run, finishedAt)} min with ${error.code}: ${message} ${run.youtube_url}`;
}

function minutesSince(run: Doc<"runs">, finishedAt: number): number {
  return Math.floor((finishedAt - run.created_at) / MINUTE_MS);
}
