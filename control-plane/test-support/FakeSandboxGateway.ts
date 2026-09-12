import type { SandboxGateway, SandboxSpec } from "../convex/sandbox/sandboxGateway";
import { SandboxGatewayError, type SandboxOperation } from "../convex/sandbox/sandboxGatewayError";

type GatewayFailure = { operation: Exclude<SandboxOperation, "delete">; message: string };

export class FakeSandboxGateway implements SandboxGateway {
  readonly createdSpecs: SandboxSpec[] = [];
  readonly startedSandboxIds: string[] = [];
  readonly deletedSandboxIds: string[] = [];

  constructor(private readonly failure: GatewayFailure | null = null) {}

  async create(spec: SandboxSpec): Promise<string> {
    this.failIf("create");
    this.createdSpecs.push(spec);
    return `sandbox-${this.createdSpecs.length}`;
  }

  async startWorker(sandboxId: string): Promise<void> {
    this.failIf("start");
    this.startedSandboxIds.push(sandboxId);
  }

  async delete(sandboxId: string): Promise<void> {
    this.deletedSandboxIds.push(sandboxId);
  }

  specFor(runId: string): SandboxSpec {
    const spec = this.createdSpecs.find((createdSpec) => createdSpec.labels.run_id === runId);
    if (spec === undefined) {
      throw new Error(`no sandbox was created for run ${runId}`);
    }
    return spec;
  }

  runToken(runId: string): string {
    const token = this.specFor(runId).envVars.KONSPEKT_RUN_TOKEN;
    if (token === undefined) {
      throw new Error(`sandbox of run ${runId} has no KONSPEKT_RUN_TOKEN`);
    }
    return token;
  }

  private failIf(operation: GatewayFailure["operation"]): void {
    if (this.failure?.operation === operation) {
      throw new SandboxGatewayError(operation, new Error(this.failure.message));
    }
  }
}
