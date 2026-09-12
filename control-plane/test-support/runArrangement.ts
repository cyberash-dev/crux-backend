import type { Id } from "../convex/_generated/dataModel";
import { sha256Hex } from "../convex/security/sha256";
import type { ControlPlane } from "./controlPlane";

export const ARRANGED_SANDBOX_ID = "sandbox-arranged";

export async function insertActiveRun(
  controlPlane: ControlPlane,
  token: string,
  status: "provisioning" | "running" = "provisioning",
): Promise<string> {
  const tokenHash = await sha256Hex(token);
  return controlPlane.run(async (ctx) => {
    const now = Date.now();
    return ctx.db.insert("runs", {
      video_id: "ZA-tUyM_y7s",
      youtube_url: "https://www.youtube.com/watch?v=ZA-tUyM_y7s",
      lang: "auto",
      status,
      stages: [],
      token_hash: tokenHash,
      sandbox_id: ARRANGED_SANDBOX_ID,
      last_event_at: now,
      created_at: now,
      updated_at: now,
    });
  });
}

export async function storedRunId(controlPlane: ControlPlane, runId: string): Promise<Id<"runs">> {
  const id = await controlPlane.run(async (ctx) => ctx.db.normalizeId("runs", runId));
  if (id === null) {
    throw new Error(`${runId} is not a run id`);
  }
  return id;
}

export async function storedFileId(controlPlane: ControlPlane, content: string): Promise<string> {
  return controlPlane.run(async (ctx) => ctx.storage.store(new Blob([content])));
}

export function lectureResult(): Record<string, unknown> {
  return {
    video: { video_id: "ZA-tUyM_y7s", title: "Lecture 1", channel: "Physics", duration_seconds: 3600 },
    outline: {
      lecture_title: "Lecture 1",
      sections: [
        { section_id: "s1", title: "Intro", start_seconds: 0, end_seconds: 600, subsections: [] },
        { section_id: "s2", title: "Waves", start_seconds: 600, end_seconds: 3600, subsections: [] },
      ],
    },
    sections: [
      { section_id: "s1", title: "Intro", source_spans: [[0, 600]], blocks: [{ kind: "paragraph", text: "Hi" }] },
      { section_id: "s2", title: "Waves", source_spans: [[600, 3600]], blocks: [] },
    ],
    claims: [{ claim_id: "c1", text: "Light is a wave", verdict: "supported" }],
    quiz: { format_version: 2, lecture_title: "Lecture 1", language: "en", questions: [] },
    cut_log: [{ start_seconds: 10, end_seconds: 20, label: "noise", reason: "silence" }],
    llm_spend_usd: 1.25,
  };
}

export function succeededCompletion(files: readonly Record<string, unknown>[]): Record<string, unknown> {
  return { status: "succeeded", result: lectureResult(), files };
}
