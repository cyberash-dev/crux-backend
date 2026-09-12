import { type Infer, v } from "convex/values";
import { EXAM_STATUSES, MESSAGE_ROLES, QUESTION_STATUSES, VERDICTS } from "./examVocabulary";

export const examStatusValidator = v.union(...EXAM_STATUSES.map((status) => v.literal(status)));

export const questionStatusValidator = v.union(
  ...QUESTION_STATUSES.map((status) => v.literal(status)),
);

export const messageRoleValidator = v.union(...MESSAGE_ROLES.map((role) => v.literal(role)));

export const verdictValidator = v.union(...VERDICTS.map((verdict) => v.literal(verdict)));

export const questionProgressValidator = v.object({
  question_id: v.string(),
  section_title: v.string(),
  status: questionStatusValidator,
  attempts: v.number(),
});
export type QuestionProgress = Infer<typeof questionProgressValidator>;

export const examProgressValidator = v.object({
  total: v.number(),
  mastered: v.number(),
  current_question_id: v.union(v.string(), v.null()),
  questions: v.array(questionProgressValidator),
});
export type ExamProgress = Infer<typeof examProgressValidator>;

export const gradedAnswerValidator = v.object({
  question_id: v.string(),
  verdict: verdictValidator,
});
export type GradedAnswer = Infer<typeof gradedAnswerValidator>;

export const examinerTurnValidator = v.object({
  state_json: v.string(),
  progress: examProgressValidator,
  examiner_message: v.string(),
  graded: v.union(gradedAnswerValidator, v.null()),
  is_mastered: v.boolean(),
});
export type ExaminerTurn = Infer<typeof examinerTurnValidator>;
