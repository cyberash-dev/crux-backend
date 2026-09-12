import type { Doc } from "../_generated/dataModel";
import type { QueryCtx } from "../_generated/server";
import type { FileKind } from "./runVocabulary";

export type StoredRunFile = {
  kind: FileKind;
  name: string;
  url: string;
  size_bytes: number;
  content_type: string;
};

export type StoredRunResult = {
  run_id: string;
  video: { video_id: string; title: string; channel: string; duration_seconds: number };
  outline_json: string;
  section_jsons: string[];
  claims_json: string;
  quiz_json: string;
  cut_log_json: string;
  files: StoredRunFile[];
};

export async function storedRunResult(ctx: QueryCtx, run: Doc<"runs">): Promise<StoredRunResult> {
  const result = await ctx.db
    .query("run_results")
    .withIndex("by_run_id", (q) => q.eq("run_id", run._id))
    .unique();
  if (result === null) {
    throw new Error(`succeeded run ${run._id} has no stored result`);
  }
  const sections = await ctx.db
    .query("run_sections")
    .withIndex("by_run_id_and_position", (q) => q.eq("run_id", run._id))
    .collect();
  const files = await ctx.db
    .query("run_files")
    .withIndex("by_run_id", (q) => q.eq("run_id", run._id))
    .collect();
  return {
    run_id: run._id,
    video: result.video,
    outline_json: result.outline_json,
    section_jsons: sections.map((section) => section.section_json),
    claims_json: result.claims_json,
    quiz_json: result.quiz_json,
    cut_log_json: result.cut_log_json,
    files: await Promise.all(files.map((file) => storedRunFile(ctx, file))),
  };
}

async function storedRunFile(ctx: QueryCtx, file: Doc<"run_files">): Promise<StoredRunFile> {
  const url = await ctx.storage.getUrl(file.storage_id);
  if (url === null) {
    throw new Error(`stored file ${file.storage_id} of run ${file.run_id} is missing`);
  }
  return {
    kind: file.kind,
    name: file.name,
    url,
    size_bytes: file.size_bytes,
    content_type: file.content_type,
  };
}
