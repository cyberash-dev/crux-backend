import { isJsonObject } from "./jsonBody";
import { invalid, type RequestValidation, valid } from "./requestValidation";

const MAX_TEXT_CHARACTERS = 4000;

export type ExamMessageRequest = { text: string };

export function examMessageRequest(body: unknown): RequestValidation<ExamMessageRequest> {
  if (!isJsonObject(body)) {
    return invalid("body must be a JSON object");
  }
  const { text } = body;
  if (typeof text !== "string") {
    return invalid("text must be a string");
  }
  const characterCount = Array.from(text).length;
  if (characterCount === 0 || characterCount > MAX_TEXT_CHARACTERS) {
    return invalid(`text must have 1 to ${MAX_TEXT_CHARACTERS} characters`);
  }
  return valid({ text });
}
