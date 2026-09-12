import { vi } from "vitest";
import { daytonaExaminerGateway } from "../convex/sandbox/examinerGatewayFactory";
import { type ControlPlane, controlPlaneWithFakeClock } from "./controlPlane";
import { FakeExaminerGateway } from "./FakeExaminerGateway";
import { postWorker } from "./httpCalls";
import { insertActiveRun, storedFileId, succeededCompletion } from "./runArrangement";

export const EXAMINER_SNAPSHOT = "konspekt-examiner-test-snapshot";
export const LECTURE_NOTES = "# Lecture 1\n\nWaves carry energy.";
export const OPEN_MESSAGE = "Lecture 1. Question 1: What does a wave carry? A) mass B) energy C) charge D) spin";
export const SECOND_QUESTION_MESSAGE = "Correct. Question 2: What is a wavelength? A) ... B) ... C) ... D) ...";
export const CLOSING_MESSAGE = "Correct. You have mastered every question of the lecture.";

type QuestionStatus = "pending" | "failed" | "mastered";

const RUN_TOKEN = "exam-run-token";

export function examControlPlane(): ControlPlane {
  const controlPlane = controlPlaneWithFakeClock();
  vi.stubEnv("EXAMINER_SNAPSHOT", EXAMINER_SNAPSHOT);
  return controlPlane;
}

/* Callers must vi.mock("./sandbox/examinerGatewayFactory") so that the
   examiner actions receive this fake instead of a Daytona client. */
export function fakeExaminerInUse(createFailure: string | null = null): FakeExaminerGateway {
  const gateway = new FakeExaminerGateway(createFailure);
  vi.mocked(daytonaExaminerGateway).mockReturnValue(gateway);
  return gateway;
}

export async function succeededRunId(controlPlane: ControlPlane): Promise<string> {
  const runId = await insertActiveRun(controlPlane, RUN_TOKEN, "running");
  const notesId = await storedFileId(controlPlane, LECTURE_NOTES);
  await postWorker(controlPlane, { runId, endpoint: "complete" }, RUN_TOKEN, succeededCompletion([
    {
      kind: "markdown",
      name: "konspekt.md",
      storage_id: notesId,
      size_bytes: LECTURE_NOTES.length,
      content_type: "text/markdown",
    },
  ]));
  return runId;
}

export function examProgress(
  statuses: readonly [QuestionStatus, QuestionStatus],
  currentQuestionId: string | null,
): Record<string, unknown> {
  return {
    total: 2,
    mastered: statuses.filter((status) => status === "mastered").length,
    current_question_id: currentQuestionId,
    questions: [
      { question_id: "q1", section_title: "Intro", status: statuses[0], attempts: statuses[0] === "pending" ? 0 : 1 },
      { question_id: "q2", section_title: "Waves", status: statuses[1], attempts: statuses[1] === "pending" ? 0 : 1 },
    ],
  };
}

export function openTurnOutput(): Record<string, unknown> {
  return {
    state: { turn: 1, queue: ["q1", "q2"] },
    progress: examProgress(["pending", "pending"], "q1"),
    examiner_message: OPEN_MESSAGE,
    graded: null,
    is_mastered: false,
    llm_spend_usd: 0,
  };
}

export function firstAnswerCorrectOutput(): Record<string, unknown> {
  return {
    state: { turn: 2, queue: ["q2"] },
    progress: examProgress(["mastered", "pending"], "q2"),
    examiner_message: SECOND_QUESTION_MESSAGE,
    graded: { question_id: "q1", verdict: "correct" },
    is_mastered: false,
    llm_spend_usd: 0.01,
  };
}

export function lastAnswerCorrectOutput(): Record<string, unknown> {
  return {
    state: { turn: 3, queue: [] },
    progress: examProgress(["mastered", "mastered"], null),
    examiner_message: CLOSING_MESSAGE,
    graded: { question_id: "q2", verdict: "correct" },
    is_mastered: true,
    llm_spend_usd: 0.01,
  };
}
