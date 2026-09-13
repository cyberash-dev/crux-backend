import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";
import {
  examProgressValidator,
  examStatusValidator,
  messageRoleValidator,
  verdictValidator,
} from "./model/examValidators";
import {
  completedStageValidator,
  fileKindValidator,
  runErrorValidator,
  runLangValidator,
  runStatusValidator,
  videoValidator,
} from "./model/runValidators";

export default defineSchema({
  runs: defineTable({
    video_id: v.string(),
    youtube_url: v.string(),
    lang: runLangValidator,
    external_ref: v.optional(v.string()),
    idempotency_key: v.optional(v.string()),
    status: runStatusValidator,
    stages: v.array(completedStageValidator),
    error: v.optional(runErrorValidator),
    llm_spend_usd: v.optional(v.number()),
    token_hash: v.optional(v.string()),
    sandbox_id: v.optional(v.string()),
    proxy_index: v.optional(v.number()),
    blocked_proxy_indexes: v.optional(v.array(v.number())),
    last_event_at: v.number(),
    created_at: v.number(),
    updated_at: v.number(),
  })
    .index("by_status_and_created_at", ["status", "created_at"])
    .index("by_idempotency_key", ["idempotency_key"]),

  /* One document counting the proxy turns taken by sandbox creations; a
     turn modulo the PROXY_URL list length is the index of its proxy. */
  proxy_rotation: defineTable({
    turns_taken: v.number(),
  }),

  /* Pipeline payloads are kept as JSON text: their shapes belong to the
     pipeline contracts, and Convex values restrict nested keys and depth. */
  run_results: defineTable({
    run_id: v.id("runs"),
    video: videoValidator,
    outline_json: v.string(),
    claims_json: v.string(),
    quiz_json: v.string(),
    cut_log_json: v.string(),
  }).index("by_run_id", ["run_id"]),

  run_sections: defineTable({
    run_id: v.id("runs"),
    position: v.number(),
    section_json: v.string(),
  }).index("by_run_id_and_position", ["run_id", "position"]),

  run_files: defineTable({
    run_id: v.id("runs"),
    kind: fileKindValidator,
    name: v.string(),
    storage_id: v.id("_storage"),
    size_bytes: v.number(),
    content_type: v.string(),
  }).index("by_run_id", ["run_id"]),

  /* exam_id is minted before the examiner sandbox exists so the sandbox can
     carry it as a label, while the exam itself is written only after the
     open turn succeeds. state_json is the examiner's opaque state. */
  exams: defineTable({
    exam_id: v.string(),
    run_id: v.id("runs"),
    status: examStatusValidator,
    state_json: v.string(),
    progress: examProgressValidator,
    sandbox_id: v.string(),
    turn_claimed_at: v.optional(v.number()),
    created_at: v.number(),
    updated_at: v.number(),
  }).index("by_exam_id", ["exam_id"]),

  exam_messages: defineTable({
    exam_id: v.string(),
    seq: v.number(),
    role: messageRoleValidator,
    text: v.string(),
    question_id: v.optional(v.string()),
    verdict: v.optional(verdictValidator),
    created_at: v.number(),
  }).index("by_exam_id_and_seq", ["exam_id", "seq"]),
});
