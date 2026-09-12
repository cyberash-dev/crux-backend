const BEARER_HEADER = /^Bearer\s+(\S+)\s*$/i;

export function bearerToken(request: Request): string | null {
  const header = request.headers.get("Authorization");
  return header === null ? null : (BEARER_HEADER.exec(header)?.[1] ?? null);
}
