"use node";

import {
  type CreateSandboxFromSnapshotParams,
  DaytonaNotFoundError,
  DaytonaTimeoutError,
} from "@daytona/sdk";
import type {
  ExaminerFile,
  ExaminerGateway,
  ExaminerSandboxSpec,
  TurnCommandResult,
} from "./examinerGateway";
import { SandboxCommandTimeoutError } from "./sandboxCommandTimeoutError";
import { SandboxGatewayError, type SandboxOperation } from "./sandboxGatewayError";
import { SandboxNotFoundError } from "./sandboxNotFoundError";

const MATERIALS_DIR = "/root/exam";
const TURN_ERROR_FILE = `${MATERIALS_DIR}/turn.err`;
/* Daytona merges stderr into the command result and does not run the
   command through a shell, so sh applies the redirect that keeps stderr in
   a file and leaves only the turn's JSON on stdout. */
const TURN_COMMAND = `sh -c 'konspekt-exam-turn ${MATERIALS_DIR} 2>${TURN_ERROR_FILE}'`;
const TURN_TIMEOUT_SECONDS = 120;
const TURN_ERROR_TAIL_COMMAND = `tail -c 2000 ${TURN_ERROR_FILE}`;
const TURN_ERROR_TAIL_TIMEOUT_SECONDS = 10;
const IDLE_STOP_MINUTES = 15;

export interface DaytonaExaminerSandbox {
  readonly id: string;
  readonly fs: { uploadFile(file: Buffer, remotePath: string): Promise<void> };
  readonly process: {
    executeCommand(
      command: string,
      cwd?: string,
      env?: Record<string, string>,
      timeout?: number,
    ): Promise<{ exitCode: number; result: string }>;
  };
  delete(): Promise<void>;
}

export interface DaytonaExaminerClient {
  create(params: CreateSandboxFromSnapshotParams): Promise<DaytonaExaminerSandbox>;
  get(sandboxId: string): Promise<DaytonaExaminerSandbox>;
}

export class DaytonaExaminerGateway implements ExaminerGateway {
  constructor(private readonly client: DaytonaExaminerClient) {}

  async create(spec: ExaminerSandboxSpec): Promise<string> {
    try {
      const sandbox = await this.client.create({
        snapshot: spec.snapshot,
        envVars: spec.envVars,
        labels: spec.labels,
        ephemeral: true,
        autoStopInterval: IDLE_STOP_MINUTES,
      });
      return sandbox.id;
    } catch (error) {
      throw new SandboxGatewayError("create", error);
    }
  }

  async upload(sandboxId: string, file: ExaminerFile): Promise<void> {
    try {
      const sandbox = await this.client.get(sandboxId);
      await sandbox.fs.uploadFile(Buffer.from(file.content), `${MATERIALS_DIR}/${file.name}`);
    } catch (error) {
      throw sandboxFailure("upload", sandboxId, error);
    }
  }

  async runTurn(sandboxId: string): Promise<TurnCommandResult> {
    try {
      return await this.commandResult(sandboxId, TURN_COMMAND, TURN_TIMEOUT_SECONDS);
    } catch (error) {
      if (error instanceof DaytonaTimeoutError) {
        throw new SandboxCommandTimeoutError(sandboxId, error);
      }
      throw sandboxFailure("command", sandboxId, error);
    }
  }

  async turnErrorTail(sandboxId: string): Promise<string> {
    try {
      const result = await this.commandResult(
        sandboxId,
        TURN_ERROR_TAIL_COMMAND,
        TURN_ERROR_TAIL_TIMEOUT_SECONDS,
      );
      return result.stdout;
    } catch (error) {
      throw sandboxFailure("command", sandboxId, error);
    }
  }

  async delete(sandboxId: string): Promise<void> {
    try {
      const sandbox = await this.client.get(sandboxId);
      await sandbox.delete();
    } catch (error) {
      throw sandboxFailure("delete", sandboxId, error);
    }
  }

  private async commandResult(
    sandboxId: string,
    command: string,
    timeoutSeconds: number,
  ): Promise<TurnCommandResult> {
    const sandbox = await this.client.get(sandboxId);
    const response = await sandbox.process.executeCommand(command, undefined, undefined, timeoutSeconds);
    return { exitCode: response.exitCode, stdout: response.result };
  }
}

function sandboxFailure(operation: SandboxOperation, sandboxId: string, error: unknown): Error {
  return error instanceof DaytonaNotFoundError
    ? new SandboxNotFoundError(sandboxId, error)
    : new SandboxGatewayError(operation, error);
}
