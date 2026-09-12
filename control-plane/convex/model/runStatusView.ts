import type { Doc } from "../_generated/dataModel";
import type { RunStatus, StageName } from "./runVocabulary";

export type RunStatusView = {
  run_id: string;
  external_ref: string | null;
  video_id: string;
  status: RunStatus;
  stages: { name: StageName; completed_at: string }[];
  error: { code: string; message: string } | null;
  llm_spend_usd: number | null;
  created_at: string;
  updated_at: string;
};

export function runStatusView(run: Doc<"runs">): RunStatusView {
  return {
    run_id: run._id,
    external_ref: run.external_ref ?? null,
    video_id: run.video_id,
    status: run.status,
    stages: run.stages.map((stage) => ({ name: stage.name, completed_at: isoTime(stage.completed_at) })),
    error: run.error ?? null,
    llm_spend_usd: run.llm_spend_usd ?? null,
    created_at: isoTime(run.created_at),
    updated_at: isoTime(run.updated_at),
  };
}

function isoTime(epochMilliseconds: number): string {
  return new Date(epochMilliseconds).toISOString();
}
