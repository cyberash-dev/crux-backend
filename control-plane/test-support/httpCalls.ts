import { isJsonObject } from "../convex/httpBoundary/jsonBody";
import { type ControlPlane, SENTINEL_SECRETS } from "./controlPlane";

export type WorkerEndpoint = "events" | "upload-url" | "complete";

export function serviceAuthorization(): Record<string, string> {
  return { Authorization: `Bearer ${SENTINEL_SECRETS.SERVICE_API_KEY}` };
}

export async function postRun(
  controlPlane: ControlPlane,
  body: unknown,
  headers: Record<string, string> = serviceAuthorization(),
): Promise<Response> {
  return controlPlane.fetch("/v1/runs", {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getRun(controlPlane: ControlPlane, path: string): Promise<Response> {
  return controlPlane.fetch(`/v1/runs/${path}`, { headers: serviceAuthorization() });
}

export async function postWorker(
  controlPlane: ControlPlane,
  path: { runId: string; endpoint: WorkerEndpoint },
  token: string,
  body: unknown,
): Promise<Response> {
  return controlPlane.fetch(`/worker/runs/${path.runId}/${path.endpoint}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function jsonObjectOf(response: Response): Promise<Record<string, unknown>> {
  const body: unknown = await response.json();
  if (!isJsonObject(body)) {
    throw new Error(`response body is not a JSON object: ${JSON.stringify(body)}`);
  }
  return body;
}

export async function submittedRunId(
  controlPlane: ControlPlane,
  youtubeUrl: string,
  lang = "auto",
): Promise<string> {
  const response = await postRun(controlPlane, { youtube_url: youtubeUrl, lang });
  const body = await jsonObjectOf(response);
  if (response.status !== 202 || typeof body.run_id !== "string") {
    throw new Error(`run was not accepted: ${response.status} ${JSON.stringify(body)}`);
  }
  return body.run_id;
}

export async function runStatusOf(
  controlPlane: ControlPlane,
  runId: string,
): Promise<Record<string, unknown>> {
  return jsonObjectOf(await getRun(controlPlane, runId));
}
