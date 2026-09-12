import { isJsonObject, isNonNegativeInteger } from "./jsonBody";
import { invalid, type RequestValidation, valid } from "./requestValidation";

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export type UploadUrlRequest = { name: string; contentType: string; sizeBytes: number };

export function uploadUrlRequest(body: unknown): RequestValidation<UploadUrlRequest> {
  if (!isJsonObject(body)) {
    return invalid("body must be a JSON object");
  }
  const { name, content_type: contentType, size_bytes: sizeBytes } = body;
  if (typeof name !== "string" || name === "") {
    return invalid("name must be a non-empty string");
  }
  if (typeof contentType !== "string" || contentType === "") {
    return invalid("content_type must be a non-empty string");
  }
  if (!isNonNegativeInteger(sizeBytes)) {
    return invalid("size_bytes must be a non-negative integer");
  }
  return valid({ name, contentType, sizeBytes });
}
