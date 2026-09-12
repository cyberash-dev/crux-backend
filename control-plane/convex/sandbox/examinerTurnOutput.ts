import {
  isJsonArray,
  isJsonObject,
  isNonNegativeInteger,
  isNonNegativeNumber,
  parsedJson,
} from "../httpBoundary/jsonBody";
import { invalid, type RequestValidation, valid } from "../httpBoundary/requestValidation";
import type { ExaminerTurn, ExamProgress, GradedAnswer, QuestionProgress } from "../model/examValidators";
import { QUESTION_STATUSES, VERDICTS } from "../model/examVocabulary";
import { isOneOf } from "../model/runVocabulary";

export function examinerTurnOutput(stdout: string): RequestValidation<ExaminerTurn> {
  const output = parsedJson(stdout);
  if (output.kind === "malformed" || !isJsonObject(output.value)) {
    return invalid("stdout is not a JSON object");
  }
  const { state, progress, examiner_message: examinerMessage, graded, is_mastered: isMastered } = output.value;
  if (!isJsonObject(state)) {
    return invalid("state must be an object");
  }
  const turnProgress = examProgress(progress);
  if (turnProgress === null) {
    return invalid("progress needs total, mastered, current_question_id and questions");
  }
  if (typeof examinerMessage !== "string" || typeof isMastered !== "boolean") {
    return invalid("examiner_message must be a string and is_mastered a boolean");
  }
  const gradedAnswer = graded === null ? null : gradedAnswerOf(graded);
  if (graded !== null && gradedAnswer === null) {
    return invalid("graded must be null or {question_id, verdict: correct|incorrect}");
  }
  if (!isNonNegativeNumber(output.value.llm_spend_usd)) {
    return invalid("llm_spend_usd must be a non-negative number");
  }
  return valid({
    state_json: JSON.stringify(state),
    progress: turnProgress,
    examiner_message: examinerMessage,
    graded: gradedAnswer,
    is_mastered: isMastered,
  });
}

function examProgress(progress: unknown): ExamProgress | null {
  if (!isJsonObject(progress)) {
    return null;
  }
  const { total, mastered, current_question_id: currentQuestionId, questions } = progress;
  if (!isNonNegativeInteger(total) || !isNonNegativeInteger(mastered) || !isJsonArray(questions)) {
    return null;
  }
  if (currentQuestionId !== null && typeof currentQuestionId !== "string") {
    return null;
  }
  const questionProgress = questions.map(questionProgressOf);
  if (questionProgress.some((question) => question === null)) {
    return null;
  }
  return {
    total,
    mastered,
    current_question_id: currentQuestionId,
    questions: questionProgress.filter((question) => question !== null),
  };
}

function questionProgressOf(question: unknown): QuestionProgress | null {
  if (!isJsonObject(question)) {
    return null;
  }
  const { question_id: questionId, section_title: sectionTitle, status, attempts } = question;
  if (typeof questionId !== "string" || typeof sectionTitle !== "string") {
    return null;
  }
  if (typeof status !== "string" || !isOneOf(QUESTION_STATUSES, status) || !isNonNegativeInteger(attempts)) {
    return null;
  }
  return { question_id: questionId, section_title: sectionTitle, status, attempts };
}

function gradedAnswerOf(graded: unknown): GradedAnswer | null {
  if (!isJsonObject(graded)) {
    return null;
  }
  const { question_id: questionId, verdict } = graded;
  if (typeof questionId !== "string" || typeof verdict !== "string" || !isOneOf(VERDICTS, verdict)) {
    return null;
  }
  return { question_id: questionId, verdict };
}
