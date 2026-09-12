export class SandboxCommandTimeoutError extends Error {
  constructor(
    readonly sandboxId: string,
    cause: unknown,
  ) {
    super(`command in sandbox ${sandboxId} timed out`, { cause });
    this.name = "SandboxCommandTimeoutError";
  }
}
