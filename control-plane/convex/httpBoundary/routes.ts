import { isOneOf } from "../model/runVocabulary";

const CLIENT_RUN_PATH = /^\/v1\/runs\/([^/]+)(\/result)?$/;
const WORKER_RUN_PATH = /^\/worker\/runs\/([^/]+)\/([^/]+)$/;
const WORKER_ENDPOINTS = ["events", "upload-url", "complete"] as const;
const EXAM_OPEN_PATH = /^\/v1\/runs\/([^/]+)\/exams$/;
const EXAM_PATH = /^\/v1\/exams\/([^/]+)(?:\/([^/]+))?$/;
const EXAM_SUB_ENDPOINTS = ["messages", "close"] as const;

export type ClientReadRoute = { endpoint: "status" | "result"; runId: string };

export type ExamRoute = { endpoint: "exam" | (typeof EXAM_SUB_ENDPOINTS)[number]; examId: string };

export type WorkerRoute = { endpoint: (typeof WORKER_ENDPOINTS)[number]; runId: string };

export function clientReadRoute(pathname: string): ClientReadRoute | null {
  const match = CLIENT_RUN_PATH.exec(pathname);
  const runId = match?.[1];
  if (match === null || runId === undefined) {
    return null;
  }
  return { endpoint: match[2] === undefined ? "status" : "result", runId };
}

export function examOpenRunId(pathname: string): string | null {
  return EXAM_OPEN_PATH.exec(pathname)?.[1] ?? null;
}

export function examRoute(pathname: string): ExamRoute | null {
  const match = EXAM_PATH.exec(pathname);
  const examId = match?.[1];
  if (match === null || examId === undefined) {
    return null;
  }
  const subEndpoint = match[2];
  if (subEndpoint === undefined) {
    return { endpoint: "exam", examId };
  }
  return isOneOf(EXAM_SUB_ENDPOINTS, subEndpoint) ? { endpoint: subEndpoint, examId } : null;
}

export function workerRoute(pathname: string): WorkerRoute | null {
  const match = WORKER_RUN_PATH.exec(pathname);
  const runId = match?.[1];
  const endpoint = match?.[2];
  if (runId === undefined || endpoint === undefined || !isOneOf(WORKER_ENDPOINTS, endpoint)) {
    return null;
  }
  return { endpoint, runId };
}
