export const RUN_STATUSES = ["queued", "provisioning", "running", "succeeded", "failed"] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

export const ACTIVE_RUN_STATUSES = ["provisioning", "running"] as const;

export const RUN_LANGS = ["auto", "ru", "en"] as const;
export type RunLang = (typeof RUN_LANGS)[number];

export const STAGE_NAMES = [
  "download",
  "ingest",
  "transcription",
  "visual",
  "segmentation",
  "factcheck",
  "notes",
  "quiz",
  "compose",
] as const;
export type StageName = (typeof STAGE_NAMES)[number];

export const FILE_KINDS = ["pdf", "markdown", "image"] as const;
export type FileKind = (typeof FILE_KINDS)[number];

export const WORKER_ERROR_CODES = [
  "VIDEO_UNAVAILABLE",
  "DOWNLOAD_FAILED",
  "CONFIGURATION_ERROR",
  "PIPELINE_FAILED",
] as const;
export type WorkerErrorCode = (typeof WORKER_ERROR_CODES)[number];

export function isOneOf<T extends string>(vocabulary: readonly T[], value: string): value is T {
  return (vocabulary as readonly string[]).includes(value);
}

export function isTerminalStatus(status: RunStatus): boolean {
  return status === "succeeded" || status === "failed";
}
