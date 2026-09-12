export type SandboxOperation = "create" | "start" | "delete" | "upload" | "command";

export class SandboxGatewayError extends Error {
  constructor(
    readonly operation: SandboxOperation,
    cause: unknown,
  ) {
    super(`sandbox ${operation} failed: ${cause instanceof Error ? cause.message : String(cause)}`, {
      cause,
    });
    this.name = "SandboxGatewayError";
  }
}
