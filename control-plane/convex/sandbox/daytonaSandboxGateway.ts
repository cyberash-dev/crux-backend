import type { CreateSandboxFromSnapshotParams } from "@daytona/sdk";
import type { SandboxGateway, SandboxSpec } from "./sandboxGateway";
import { SandboxGatewayError } from "./sandboxGatewayError";

const WORKER_SESSION_ID = "konspekt-worker";
const WORKER_COMMAND = "konspekt-worker > /root/worker.log 2>&1";
const AUTO_STOP_DISABLED = 0;
const SANDBOX_TTL_MINUTES = 240;

export interface DaytonaSandbox {
  readonly id: string;
  readonly process: {
    createSession(sessionId: string): Promise<void>;
    executeSessionCommand(
      sessionId: string,
      request: { command: string; runAsync: boolean },
    ): Promise<unknown>;
  };
  delete(): Promise<void>;
}

export interface DaytonaClient {
  create(params: CreateSandboxFromSnapshotParams): Promise<DaytonaSandbox>;
  get(sandboxId: string): Promise<DaytonaSandbox>;
}

export class DaytonaSandboxGateway implements SandboxGateway {
  constructor(private readonly client: DaytonaClient) {}

  async create(spec: SandboxSpec): Promise<string> {
    try {
      const sandbox = await this.client.create({
        snapshot: spec.snapshot,
        outboundProxyUrl: spec.outboundProxyUrl,
        envVars: spec.envVars,
        labels: spec.labels,
        autoStopInterval: AUTO_STOP_DISABLED,
        ttlMinutes: SANDBOX_TTL_MINUTES,
      });
      return sandbox.id;
    } catch (error) {
      throw new SandboxGatewayError("create", error);
    }
  }

  async startWorker(sandboxId: string): Promise<void> {
    try {
      const sandbox = await this.client.get(sandboxId);
      await sandbox.process.createSession(WORKER_SESSION_ID);
      await sandbox.process.executeSessionCommand(WORKER_SESSION_ID, {
        command: WORKER_COMMAND,
        runAsync: true,
      });
    } catch (error) {
      throw new SandboxGatewayError("start", error);
    }
  }

  async delete(sandboxId: string): Promise<void> {
    try {
      const sandbox = await this.client.get(sandboxId);
      await sandbox.delete();
    } catch (error) {
      throw new SandboxGatewayError("delete", error);
    }
  }
}
