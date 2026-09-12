export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function errorResponse(status: number, code: string, message: string): Response {
  return jsonResponse(status, { error: { code, message } });
}

export function invalidRequestResponse(message: string): Response {
  return errorResponse(422, "INVALID_REQUEST", message);
}

export function unauthorizedResponse(): Response {
  return errorResponse(401, "UNAUTHORIZED", "missing or wrong credentials");
}

export function notFoundResponse(): Response {
  return errorResponse(404, "NOT_FOUND", "no such endpoint");
}

export function noContentResponse(): Response {
  return new Response(null, { status: 204 });
}
