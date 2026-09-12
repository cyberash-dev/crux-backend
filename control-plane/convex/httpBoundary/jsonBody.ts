export type JsonBody = { kind: "parsed"; value: unknown } | { kind: "malformed" };

export async function jsonBody(request: Request): Promise<JsonBody> {
  return parsedJson(await request.text());
}

export function parsedJson(text: string): JsonBody {
  try {
    const value: unknown = JSON.parse(text);
    return { kind: "parsed", value };
  } catch (error) {
    if (error instanceof SyntaxError) {
      return { kind: "malformed" };
    }
    throw error;
  }
}

export function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isJsonArray(value: unknown): value is readonly unknown[] {
  return Array.isArray(value);
}

export function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

export function isNonNegativeNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}
