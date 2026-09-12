import type { Doc } from "../_generated/dataModel";
import type { ExamProgress } from "./examValidators";
import type { ExamStatus } from "./examVocabulary";

export type ExamView = {
  exam_id: string;
  run_id: string;
  status: ExamStatus;
  progress: ExamProgress;
  created_at: string;
  updated_at: string;
};

export function examView(exam: Doc<"exams">): ExamView {
  return {
    exam_id: exam.exam_id,
    run_id: exam.run_id,
    status: exam.status,
    progress: exam.progress,
    created_at: new Date(exam.created_at).toISOString(),
    updated_at: new Date(exam.updated_at).toISOString(),
  };
}
