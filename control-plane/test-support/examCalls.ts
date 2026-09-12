import type { ControlPlane } from "./controlPlane";
import { jsonObjectOf, serviceAuthorization } from "./httpCalls";

export async function postOpenExam(
  controlPlane: ControlPlane,
  runId: string,
  headers: Record<string, string> = serviceAuthorization(),
): Promise<Response> {
  return controlPlane.fetch(`/v1/runs/${runId}/exams`, { method: "POST", headers });
}

export async function openedExamId(controlPlane: ControlPlane, runId: string): Promise<string> {
  const response = await postOpenExam(controlPlane, runId);
  const body = await jsonObjectOf(response);
  if (response.status !== 201 || typeof body.exam_id !== "string") {
    throw new Error(`exam was not opened: ${response.status} ${JSON.stringify(body)}`);
  }
  return body.exam_id;
}

export async function getExam(controlPlane: ControlPlane, path: string): Promise<Response> {
  return controlPlane.fetch(`/v1/exams/${path}`, { headers: serviceAuthorization() });
}

export async function postStudentMessage(
  controlPlane: ControlPlane,
  examId: string,
  body: unknown,
): Promise<Response> {
  return controlPlane.fetch(`/v1/exams/${examId}/messages`, {
    method: "POST",
    headers: { ...serviceAuthorization(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function postCloseExam(controlPlane: ControlPlane, examId: string): Promise<Response> {
  return controlPlane.fetch(`/v1/exams/${examId}/close`, { method: "POST", headers: serviceAuthorization() });
}
