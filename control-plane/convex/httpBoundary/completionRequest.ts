import type { ReportedFile, Video } from "../model/runValidators";
import {
  FILE_KINDS,
  isOneOf,
  WORKER_ERROR_CODES,
  type WorkerErrorCode,
} from "../model/runVocabulary";
import { isJsonArray, isJsonObject, isNonNegativeInteger, isNonNegativeNumber } from "./jsonBody";
import { invalid, type RequestValidation, valid } from "./requestValidation";

export type CompletedResult = {
  video: Video;
  outline: Record<string, unknown>;
  sections: readonly Record<string, unknown>[];
  claims: readonly unknown[];
  quiz: Record<string, unknown>;
  cutLog: readonly unknown[];
  llmSpendUsd: number | null;
};

export type Completion =
  | { status: "succeeded"; result: CompletedResult; files: readonly ReportedFile[] }
  | { status: "failed"; error: { code: WorkerErrorCode; message: string } };

export function completionRequest(body: unknown): RequestValidation<Completion> {
  if (!isJsonObject(body)) {
    return invalid("body must be a JSON object");
  }
  if (body.status === "succeeded") {
    return succeededCompletion(body.result, body.files);
  }
  if (body.status === "failed") {
    return failedCompletion(body.error);
  }
  return invalid("status must be succeeded or failed");
}

function succeededCompletion(result: unknown, files: unknown): RequestValidation<Completion> {
  const completedResult = resultPayload(result);
  if (completedResult.kind === "invalid") {
    return invalid(completedResult.message);
  }
  if (!isJsonArray(files)) {
    return invalid("files must be an array");
  }
  const reportedFiles = files.map(reportedFile);
  if (reportedFiles.some((file) => file === null)) {
    return invalid(
      "each file needs kind (pdf, markdown, image), name, storage_id, size_bytes and content_type",
    );
  }
  return valid({
    status: "succeeded",
    result: completedResult.value,
    files: reportedFiles.filter((file) => file !== null),
  });
}

function failedCompletion(error: unknown): RequestValidation<Completion> {
  if (!isJsonObject(error)) {
    return invalid("error must be an object with code and message");
  }
  const { code, message } = error;
  if (typeof code !== "string" || !isOneOf(WORKER_ERROR_CODES, code)) {
    return invalid(`error.code must be one of ${WORKER_ERROR_CODES.join(", ")}`);
  }
  if (typeof message !== "string") {
    return invalid("error.message must be a string");
  }
  return valid({ status: "failed", error: { code, message } });
}

function resultPayload(result: unknown): RequestValidation<CompletedResult> {
  if (!isJsonObject(result)) {
    return invalid("result must be an object");
  }
  const { video, outline, sections, claims, quiz, cut_log: cutLog, llm_spend_usd: spend } = result;
  const completedVideo = videoPayload(video);
  if (completedVideo === null) {
    return invalid("result.video needs video_id, title, channel and duration_seconds");
  }
  if (!isJsonObject(outline) || !isJsonObject(quiz)) {
    return invalid("result.outline and result.quiz must be objects");
  }
  if (!isJsonArray(sections) || !sections.every(isJsonObject)) {
    return invalid("result.sections must be an array of objects");
  }
  if (!isJsonArray(claims) || !isJsonArray(cutLog)) {
    return invalid("result.claims and result.cut_log must be arrays");
  }
  if (spend !== null && !isNonNegativeNumber(spend)) {
    return invalid("result.llm_spend_usd must be a non-negative number or null");
  }
  return valid({ video: completedVideo, outline, sections, claims, quiz, cutLog, llmSpendUsd: spend });
}

function videoPayload(video: unknown): Video | null {
  if (!isJsonObject(video)) {
    return null;
  }
  const { video_id: videoId, title, channel, duration_seconds: durationSeconds } = video;
  if (typeof videoId !== "string" || typeof title !== "string" || typeof channel !== "string") {
    return null;
  }
  if (!isNonNegativeNumber(durationSeconds)) {
    return null;
  }
  return { video_id: videoId, title, channel, duration_seconds: durationSeconds };
}

function reportedFile(file: unknown): ReportedFile | null {
  if (!isJsonObject(file)) {
    return null;
  }
  const { kind, name, storage_id: storageId, size_bytes: sizeBytes, content_type: contentType } = file;
  if (typeof kind !== "string" || !isOneOf(FILE_KINDS, kind) || !isNonNegativeInteger(sizeBytes)) {
    return null;
  }
  if (typeof name !== "string" || typeof storageId !== "string" || typeof contentType !== "string") {
    return null;
  }
  return { kind, name, storage_id: storageId, size_bytes: sizeBytes, content_type: contentType };
}
