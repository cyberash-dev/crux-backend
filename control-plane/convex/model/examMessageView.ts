import type { Doc } from "../_generated/dataModel";
import type { MessageRole, Verdict } from "./examVocabulary";

export type ExamMessage = Omit<Doc<"exam_messages">, "_id" | "_creationTime">;

export type ExamMessageView = {
  seq: number;
  role: MessageRole;
  text: string;
  question_id: string | null;
  verdict: Verdict | null;
  created_at: string;
};

export function examMessageView(message: ExamMessage): ExamMessageView {
  return {
    seq: message.seq,
    role: message.role,
    text: message.text,
    question_id: message.question_id ?? null,
    verdict: message.verdict ?? null,
    created_at: new Date(message.created_at).toISOString(),
  };
}
