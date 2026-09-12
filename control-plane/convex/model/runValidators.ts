import { type Infer, v } from "convex/values";
import {
  FILE_KINDS,
  RUN_LANGS,
  RUN_STATUSES,
  STAGE_NAMES,
  WORKER_ERROR_CODES,
} from "./runVocabulary";

export const runStatusValidator = v.union(...RUN_STATUSES.map((status) => v.literal(status)));

export const runLangValidator = v.union(...RUN_LANGS.map((lang) => v.literal(lang)));

export const stageNameValidator = v.union(...STAGE_NAMES.map((stage) => v.literal(stage)));

export const fileKindValidator = v.union(...FILE_KINDS.map((kind) => v.literal(kind)));

export const workerErrorCodeValidator = v.union(
  ...WORKER_ERROR_CODES.map((code) => v.literal(code)),
);

export const runErrorValidator = v.object({ code: v.string(), message: v.string() });

export const completedStageValidator = v.object({
  name: stageNameValidator,
  completed_at: v.number(),
});

export const videoValidator = v.object({
  video_id: v.string(),
  title: v.string(),
  channel: v.string(),
  duration_seconds: v.number(),
});
export type Video = Infer<typeof videoValidator>;

export const reportedFileValidator = v.object({
  kind: fileKindValidator,
  name: v.string(),
  storage_id: v.string(),
  size_bytes: v.number(),
  content_type: v.string(),
});
export type ReportedFile = Infer<typeof reportedFileValidator>;

export const workerEventValidator = v.union(
  v.object({ type: v.literal("stage_completed"), stage: stageNameValidator }),
  v.object({ type: v.literal("heartbeat") }),
);
export type WorkerEvent = Infer<typeof workerEventValidator>;
