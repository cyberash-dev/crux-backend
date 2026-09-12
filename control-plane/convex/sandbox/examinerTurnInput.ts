import type { MessageRole } from "../model/examVocabulary";

export type TranscriptMessage = { role: MessageRole; text: string };

export const OPEN_TURN_INPUT = JSON.stringify({ kind: "open" });

export function replyTurnInput(
  stateJson: string,
  messages: readonly TranscriptMessage[],
  studentMessage: string,
): string {
  const state: unknown = JSON.parse(stateJson);
  return JSON.stringify({ kind: "reply", state, messages, student_message: studentMessage });
}
