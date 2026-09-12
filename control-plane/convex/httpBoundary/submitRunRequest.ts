import { isOneOf, RUN_LANGS, type RunLang } from "../model/runVocabulary";
import { isJsonObject } from "./jsonBody";
import { invalid, type RequestValidation, valid } from "./requestValidation";

const MAX_EXTERNAL_REF_LENGTH = 200;

export type SubmitRunRequest = {
  youtubeUrl: string;
  lang: RunLang;
  externalRef: string | null;
};

export function submitRunRequest(body: unknown): RequestValidation<SubmitRunRequest> {
  if (!isJsonObject(body)) {
    return invalid("body must be a JSON object");
  }
  const { youtube_url: youtubeUrl, lang = "auto", external_ref: externalRef } = body;
  if (typeof youtubeUrl !== "string") {
    return invalid("youtube_url must be a string");
  }
  if (typeof lang !== "string" || !isOneOf(RUN_LANGS, lang)) {
    return invalid(`lang must be one of ${RUN_LANGS.join(", ")}`);
  }
  if (externalRef === undefined) {
    return valid({ youtubeUrl, lang, externalRef: null });
  }
  if (typeof externalRef !== "string" || externalRef.length > MAX_EXTERNAL_REF_LENGTH) {
    return invalid(`external_ref must be a string of at most ${MAX_EXTERNAL_REF_LENGTH} characters`);
  }
  return valid({ youtubeUrl, lang, externalRef });
}
