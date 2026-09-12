# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28"]
# ///
import os
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Literal, TypedDict

import httpx

DEFAULT_API_BASE = "https://stoic-bird-582.eu-west-1.convex.site"
DEFAULT_RUN_ID = "jh734jt0w3revjphkp96hpx81n8e8mmf"
REQUEST_TIMEOUT_SECONDS = 150
TURNS_PER_QUESTION = 3
OPTION_LETTERS = "ABCD"
SHOWN_MESSAGE_CHARS = 200
WRONG_OPEN_ANSWER = "I think this part of the lecture was about something else entirely."

type ExamStatus = Literal["active", "mastered", "closed"]
type QuestionStatus = Literal["pending", "failed", "mastered"]


class QuizQuestion(TypedDict):
    question_id: str
    options: list[str] | None
    correct_options: list[int] | None
    model_answer: str | None


class QuestionProgress(TypedDict):
    question_id: str
    status: QuestionStatus
    attempts: int


class Progress(TypedDict):
    total: int
    mastered: int
    current_question_id: str | None
    questions: list[QuestionProgress]


class ExamMessage(TypedDict):
    text: str
    verdict: Literal["correct", "incorrect"] | None


class ExamOpened(TypedDict):
    exam_id: str
    progress: Progress
    examiner_message: ExamMessage


class ExamReply(TypedDict):
    status: ExamStatus
    progress: Progress
    student_message: ExamMessage
    examiner_message: ExamMessage


def quiz_questions(client: httpx.Client, run_id: str) -> list[QuizQuestion]:
    response = client.get(f"/v1/runs/{run_id}/result")
    response.raise_for_status()
    questions: list[QuizQuestion] = response.json()["quiz"]["questions"]
    return questions


def preview(text: str) -> str:
    return text[:SHOWN_MESSAGE_CHARS].replace("\n", " ")


def opened_exam(client: httpx.Client, run_id: str) -> ExamOpened:
    started = time.monotonic()
    response = client.post(f"/v1/runs/{run_id}/exams")
    latency = time.monotonic() - started
    if response.status_code != 201:
        raise SystemExit(f"POST /v1/runs/{run_id}/exams -> {response.status_code} {response.text}")
    exam: ExamOpened = response.json()
    print(f"exam {exam['exam_id']} opened in {latency:.1f}s")
    print(f"  examiner: {preview(exam['examiner_message']['text'])}")
    return exam


def question_status(progress: Progress, question_id: str) -> QuestionStatus:
    return next(q["status"] for q in progress["questions"] if q["question_id"] == question_id)


def correct_answer(question: QuizQuestion, status: QuestionStatus) -> str:
    model_answer = question["model_answer"]
    options = question["options"]
    correct_options = question["correct_options"]
    if model_answer is not None:
        return model_answer
    if options is None or correct_options is None:
        raise ValueError(f"question {question['question_id']} has no answer key")
    if status == "failed":
        return "; ".join(options[index] for index in correct_options)
    return ", ".join(OPTION_LETTERS[index] for index in correct_options)


def wrong_answer(question: QuizQuestion) -> str:
    correct_options = question["correct_options"]
    if correct_options is None:
        return WRONG_OPEN_ANSWER
    wrong_index = next(
        (index for index in range(len(OPTION_LETTERS)) if index not in correct_options),
        correct_options[0],
    )
    return OPTION_LETTERS[wrong_index]


def student_reply(client: httpx.Client, exam_id: str, text: str) -> tuple[ExamReply, float]:
    started = time.monotonic()
    response = client.post(f"/v1/exams/{exam_id}/messages", json={"text": text})
    latency = time.monotonic() - started
    if response.status_code != 200:
        raise SystemExit(f"POST /v1/exams/{exam_id}/messages -> {response.status_code} {response.text}")
    reply: ExamReply = response.json()
    return reply, latency


def mastered_progress(
    client: httpx.Client, exam: ExamOpened, quiz: Sequence[QuizQuestion]
) -> Progress:
    questions: Mapping[str, QuizQuestion] = {q["question_id"]: q for q in quiz}
    first_question_id = quiz[0]["question_id"]
    turn_budget = TURNS_PER_QUESTION * len(quiz)
    progress = exam["progress"]
    is_wrong_answer_sent = False
    for turn_number in range(1, turn_budget + 1):
        question_id = progress["current_question_id"]
        if question_id is None:
            raise SystemExit(f"exam {exam['exam_id']} has no current question before it is mastered")
        is_deliberate_mistake = question_id == first_question_id and not is_wrong_answer_sent
        text = (
            wrong_answer(questions[question_id])
            if is_deliberate_mistake
            else correct_answer(questions[question_id], question_status(progress, question_id))
        )
        is_wrong_answer_sent = is_wrong_answer_sent or is_deliberate_mistake
        reply, latency = student_reply(client, exam["exam_id"], text)
        verdict = reply["student_message"]["verdict"] or "-"
        print(f"turn {turn_number:>2} {question_id:<8} {verdict:<9} {latency:5.1f}s")
        print(f"  examiner: {preview(reply['examiner_message']['text'])}")
        progress = reply["progress"]
        if reply["status"] == "mastered":
            return progress
    raise SystemExit(f"exam {exam['exam_id']} not mastered after {turn_budget} turns")


def print_final_progress(progress: Progress) -> None:
    print(f"mastered {progress['mastered']}/{progress['total']}")
    for question in progress["questions"]:
        print(f"  {question['question_id']:<8} {question['status']:<9} attempts={question['attempts']}")


def main() -> int:
    api_key = os.environ.get("SERVICE_API_KEY")
    if not api_key:
        print("SERVICE_API_KEY is not set", file=sys.stderr)
        return 2
    run_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RUN_ID
    api_base = os.environ.get("KONSPEKT_SERVICE_URL", DEFAULT_API_BASE)
    headers = {"Authorization": f"Bearer {api_key}"}
    started = time.monotonic()
    with httpx.Client(base_url=api_base, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        quiz = quiz_questions(client, run_id)
        exam = opened_exam(client, run_id)
        progress = mastered_progress(client, exam, quiz)
    print_final_progress(progress)
    print(f"total time {time.monotonic() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
