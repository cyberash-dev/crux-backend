export type RequestValidation<T> = { kind: "valid"; value: T } | { kind: "invalid"; message: string };

export function valid<T>(value: T): RequestValidation<T> {
  return { kind: "valid", value };
}

export function invalid<T>(message: string): RequestValidation<T> {
  return { kind: "invalid", message };
}
