export const EXAM_STATUSES = ["active", "mastered", "closed"] as const;
export type ExamStatus = (typeof EXAM_STATUSES)[number];

export const QUESTION_STATUSES = ["pending", "failed", "mastered"] as const;
export type QuestionStatus = (typeof QUESTION_STATUSES)[number];

export const MESSAGE_ROLES = ["examiner", "student"] as const;
export type MessageRole = (typeof MESSAGE_ROLES)[number];

export const VERDICTS = ["correct", "incorrect"] as const;
export type Verdict = (typeof VERDICTS)[number];

export const EXAM_API_ERROR_CODES = [
  "EXAM_NOT_FOUND",
  "EXAM_FINISHED",
  "EXAM_TURN_IN_PROGRESS",
  "EXAMINER_FAILED",
  "EXAMINER_TIMEOUT",
] as const;
