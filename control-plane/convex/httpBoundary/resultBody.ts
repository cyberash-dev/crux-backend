import type { StoredRunResult } from "../model/storedRunResult";

export function resultBody(result: StoredRunResult): Record<string, unknown> {
  return {
    run_id: result.run_id,
    video: result.video,
    outline: jsonValue(result.outline_json),
    sections: result.section_jsons.map(jsonValue),
    claims: jsonValue(result.claims_json),
    quiz: jsonValue(result.quiz_json),
    cut_log: jsonValue(result.cut_log_json),
    files: result.files,
  };
}

function jsonValue(text: string): unknown {
  return JSON.parse(text);
}
