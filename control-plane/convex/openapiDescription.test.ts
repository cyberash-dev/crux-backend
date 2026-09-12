/** @vitest-environment node */
/* @covers service:GEN-001 */
/* @covers service:DLT-001 */
/* @covers service:DLT-005 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";
import { parse } from "yaml";
import http from "./http";
import {
  EXAM_API_ERROR_CODES,
  EXAM_STATUSES,
  MESSAGE_ROLES,
  QUESTION_STATUSES,
  VERDICTS,
} from "./model/examVocabulary";
import {
  FILE_KINDS,
  RUN_LANGS,
  RUN_STATUSES,
  STAGE_NAMES,
  WORKER_ERROR_CODES,
} from "./model/runVocabulary";

const CONTROL_PLANE_RUN_ERROR_CODES = ["SANDBOX_START_FAILED", "WORKER_LOST"] as const;
const CLIENT_API_ERROR_CODES = [
  "UNAUTHORIZED",
  "INVALID_REQUEST",
  "INPUT_NOT_YOUTUBE",
  "RUN_NOT_FOUND",
  "RUN_NOT_FINISHED",
  "NOT_FOUND",
] as const;

function openApiDocument(): unknown {
  const documentPath = fileURLToPath(new URL("../openapi.yaml", import.meta.url));
  const document: unknown = parse(readFileSync(documentPath, "utf8"));
  return document;
}

function field(container: unknown, key: string): unknown {
  if (typeof container !== "object" || container === null || !(key in container)) {
    throw new Error(`openapi.yaml lacks the key ${key}`);
  }
  const value: unknown = Reflect.get(container, key);
  return value;
}

function schemaEnum(schemaName: string): string[] {
  const values = field(field(field(field(openApiDocument(), "components"), "schemas"), schemaName), "enum");
  if (!Array.isArray(values)) {
    throw new Error(`schema ${schemaName} has no enum`);
  }
  const strings = values.filter((value): value is string => typeof value === "string");
  if (strings.length !== values.length) {
    throw new Error(`schema ${schemaName} enum holds non-string values`);
  }
  return strings;
}

function operationMethods(): Record<string, string[]> {
  const paths = field(openApiDocument(), "paths");
  if (typeof paths !== "object" || paths === null) {
    throw new Error("openapi.yaml paths is not an object");
  }
  return Object.fromEntries(
    Object.entries(paths).map(([path, operations]) => [
      path,
      typeof operations === "object" && operations !== null ? Object.keys(operations) : [],
    ]),
  );
}

function sorted(values: readonly string[]): string[] {
  return [...values].sort();
}

describe("the published OpenAPI description matches the control plane", () => {
  test.each([
    ["RunStatusValue", RUN_STATUSES],
    ["StageName", STAGE_NAMES],
    ["Lang", RUN_LANGS],
    ["FileKind", FILE_KINDS],
    ["ExamStatus", EXAM_STATUSES],
    ["QuestionStatus", QUESTION_STATUSES],
    ["MessageRole", MESSAGE_ROLES],
    ["Verdict", VERDICTS],
  ])("schema %s lists exactly the control-plane vocabulary", (schemaName, vocabulary) => {
    expect(schemaEnum(schemaName)).toEqual([...vocabulary]);
  });

  test("run error codes cover the worker codes and the control-plane codes", () => {
    expect(sorted(schemaEnum("RunErrorCode"))).toEqual(
      sorted([...WORKER_ERROR_CODES, ...CONTROL_PLANE_RUN_ERROR_CODES]),
    );
  });

  test("client error codes list exactly what the client API returns", () => {
    expect(sorted(schemaEnum("ErrorCode"))).toEqual(
      sorted([...CLIENT_API_ERROR_CODES, ...EXAM_API_ERROR_CODES]),
    );
  });

  test("the described operations are the client API operations", () => {
    expect(operationMethods()).toEqual({
      "/v1/runs": ["post"],
      "/v1/runs/{run_id}": ["get"],
      "/v1/runs/{run_id}/result": ["get"],
      "/v1/runs/{run_id}/exams": ["post"],
      "/v1/exams/{exam_id}": ["get"],
      "/v1/exams/{exam_id}/messages": ["get", "post"],
      "/v1/exams/{exam_id}/close": ["post"],
    });
  });

  test.each([
    ["/v1/runs", "POST"],
    ["/v1/runs/jh734jt0w3revjphkp96hpx81n8e8mmf", "GET"],
    ["/v1/runs/jh734jt0w3revjphkp96hpx81n8e8mmf/result", "GET"],
    ["/v1/runs/jh734jt0w3revjphkp96hpx81n8e8mmf/exams", "POST"],
    ["/v1/exams/k97c2rv8x1h7ds0x4ntjw1d4b58e9a0q", "GET"],
    ["/v1/exams/k97c2rv8x1h7ds0x4ntjw1d4b58e9a0q/messages", "GET"],
    ["/v1/exams/k97c2rv8x1h7ds0x4ntjw1d4b58e9a0q/messages", "POST"],
    ["/v1/exams/k97c2rv8x1h7ds0x4ntjw1d4b58e9a0q/close", "POST"],
  ] as const)("the router serves %s %s", (path, method) => {
    expect(http.lookup(path, method)).not.toBeNull();
  });
});
