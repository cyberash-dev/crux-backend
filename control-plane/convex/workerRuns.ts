import { type ObjectType, v } from "convex/values";
import type { Doc, Id } from "./_generated/dataModel";
import {
  type DatabaseReader,
  type DatabaseWriter,
  internalMutation,
  internalQuery,
} from "./_generated/server";
import { finishRun } from "./model/runLifecycle";
import {
  type ReportedFile,
  reportedFileValidator,
  videoValidator,
  type WorkerEvent,
  workerErrorCodeValidator,
  workerEventValidator,
} from "./model/runValidators";
import { type WorkerAccess, workerAccess } from "./model/workerAccess";
import { redactedText } from "./security/secretRedaction";

export type WorkerAccessKind = WorkerAccess["kind"];
export type WorkerCallOutcome = "applied" | Exclude<WorkerAccessKind, "granted"> | "unknown_storage_id";

type StoredFile = Omit<ReportedFile, "storage_id"> & { storage_id: Id<"_storage"> };

const workerCallArgs = { runId: v.string(), tokenHash: v.string() };

const resultDocumentArgs = {
  video: videoValidator,
  outline_json: v.string(),
  section_jsons: v.array(v.string()),
  claims_json: v.string(),
  quiz_json: v.string(),
  cut_log_json: v.string(),
};
type ResultDocuments = ObjectType<typeof resultDocumentArgs>;

export const workerAccessKind = internalQuery({
  args: workerCallArgs,
  handler: async (ctx, { runId, tokenHash }): Promise<WorkerAccessKind> =>
    (await workerAccess(ctx.db, runId, tokenHash)).kind,
});

export const recordEvent = internalMutation({
  args: { ...workerCallArgs, event: workerEventValidator },
  handler: async (ctx, { runId, tokenHash, event }): Promise<WorkerCallOutcome> => {
    const access = await workerAccess(ctx.db, runId, tokenHash);
    if (access.kind !== "granted") {
      return access.kind;
    }
    const now = Date.now();
    await ctx.db.patch("runs", access.run._id, {
      status: "running",
      stages: stagesAfter(access.run.stages, event, now),
      last_event_at: now,
      updated_at: now,
    });
    return "applied";
  },
});

export const recordSuccess = internalMutation({
  args: {
    ...workerCallArgs,
    ...resultDocumentArgs,
    llm_spend_usd: v.union(v.number(), v.null()),
    files: v.array(reportedFileValidator),
  },
  handler: async (ctx, args): Promise<WorkerCallOutcome> => {
    const { runId, tokenHash, llm_spend_usd: spend, files: reportedFiles, ...result } = args;
    const access = await workerAccess(ctx.db, runId, tokenHash);
    if (access.kind !== "granted") {
      return access.kind;
    }
    const files = await storedFiles(ctx.db, reportedFiles);
    if (files === null) {
      return "unknown_storage_id";
    }
    await insertResultDocuments(ctx.db, access.run._id, result, files);
    await finishRun(
      ctx,
      access.run,
      spend === null ? { status: "succeeded" } : { status: "succeeded", llm_spend_usd: spend },
    );
    return "applied";
  },
});

export const recordFailure = internalMutation({
  args: {
    ...workerCallArgs,
    error: v.object({ code: workerErrorCodeValidator, message: v.string() }),
  },
  handler: async (ctx, { runId, tokenHash, error }): Promise<WorkerCallOutcome> => {
    const access = await workerAccess(ctx.db, runId, tokenHash);
    if (access.kind !== "granted") {
      return access.kind;
    }
    await finishRun(ctx, access.run, {
      status: "failed",
      error: { code: error.code, message: redactedText(error.message) },
    });
    return "applied";
  },
});

function stagesAfter(
  stages: Doc<"runs">["stages"],
  event: WorkerEvent,
  now: number,
): Doc<"runs">["stages"] {
  if (event.type !== "stage_completed" || stages.some((stage) => stage.name === event.stage)) {
    return stages;
  }
  return [...stages, { name: event.stage, completed_at: now }];
}

async function insertResultDocuments(
  db: DatabaseWriter,
  runId: Id<"runs">,
  result: ResultDocuments,
  files: readonly StoredFile[],
): Promise<void> {
  const { section_jsons: sectionJsons, ...runResult } = result;
  await db.insert("run_results", { ...runResult, run_id: runId });
  for (const [position, sectionJson] of sectionJsons.entries()) {
    await db.insert("run_sections", { run_id: runId, position, section_json: sectionJson });
  }
  for (const file of files) {
    await db.insert("run_files", { ...file, run_id: runId });
  }
}

async function storedFiles(
  db: DatabaseReader,
  files: readonly ReportedFile[],
): Promise<StoredFile[] | null> {
  const resolvedFiles = await Promise.all(files.map((file) => storedFile(db, file)));
  return resolvedFiles.every((file) => file !== null) ? resolvedFiles : null;
}

async function storedFile(db: DatabaseReader, file: ReportedFile): Promise<StoredFile | null> {
  const storageId = db.system.normalizeId("_storage", file.storage_id);
  if (storageId === null || (await db.system.get("_storage", storageId)) === null) {
    return null;
  }
  return { ...file, storage_id: storageId };
}
