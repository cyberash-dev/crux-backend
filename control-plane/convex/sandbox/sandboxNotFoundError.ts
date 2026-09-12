export class SandboxNotFoundError extends Error {
  constructor(
    readonly sandboxId: string,
    cause: unknown,
  ) {
    super(`sandbox ${sandboxId} not found`, { cause });
    this.name = "SandboxNotFoundError";
  }
}
