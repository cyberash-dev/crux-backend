import type { WorkerEvent } from "../model/runValidators";
import { isOneOf, STAGE_NAMES } from "../model/runVocabulary";
import { isJsonObject } from "./jsonBody";
import { invalid, type RequestValidation, valid } from "./requestValidation";

export function workerEventRequest(body: unknown): RequestValidation<WorkerEvent> {
  if (!isJsonObject(body)) {
    return invalid("body must be a JSON object");
  }
  if (body.type === "heartbeat") {
    return valid({ type: "heartbeat" });
  }
  if (body.type !== "stage_completed") {
    return invalid("type must be stage_completed or heartbeat");
  }
  const { stage } = body;
  if (typeof stage !== "string" || !isOneOf(STAGE_NAMES, stage)) {
    return invalid(`stage must be one of ${STAGE_NAMES.join(", ")}`);
  }
  return valid({ type: "stage_completed", stage });
}
