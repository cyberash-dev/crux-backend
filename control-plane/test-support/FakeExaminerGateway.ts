import type {
  ExaminerFile,
  ExaminerFileName,
  ExaminerGateway,
  ExaminerSandboxSpec,
  TurnCommandResult,
} from "../convex/sandbox/examinerGateway";
import { SandboxCommandTimeoutError } from "../convex/sandbox/sandboxCommandTimeoutError";
import { SandboxGatewayError } from "../convex/sandbox/sandboxGatewayError";
import { SandboxNotFoundError } from "../convex/sandbox/sandboxNotFoundError";

export type ScriptedTurn =
  | { kind: "output"; output: Record<string, unknown> }
  | { kind: "stdout"; stdout: string }
  | { kind: "exit"; exitCode: number; stderr: string }
  | { kind: "timeout" };

type Upload = { sandboxId: string; name: ExaminerFileName; text: string };

export class FakeExaminerGateway implements ExaminerGateway {
  readonly createdSpecs: ExaminerSandboxSpec[] = [];
  readonly uploads: Upload[] = [];
  readonly turnSandboxIds: string[] = [];
  readonly deletedSandboxIds: string[] = [];
  private readonly scriptedTurns: ScriptedTurn[] = [];
  private readonly lostSandboxIds = new Set<string>();
  private lastStderr = "";

  constructor(private readonly createFailure: string | null = null) {}

  answers(...turns: ScriptedTurn[]): void {
    this.scriptedTurns.push(...turns);
  }

  lose(sandboxId: string): void {
    this.lostSandboxIds.add(sandboxId);
  }

  async create(spec: ExaminerSandboxSpec): Promise<string> {
    if (this.createFailure !== null) {
      throw new SandboxGatewayError("create", new Error(this.createFailure));
    }
    this.createdSpecs.push(spec);
    return `examiner-sandbox-${this.createdSpecs.length}`;
  }

  async upload(sandboxId: string, file: ExaminerFile): Promise<void> {
    this.failIfLost(sandboxId);
    this.uploads.push({ sandboxId, name: file.name, text: new TextDecoder().decode(file.content) });
  }

  async runTurn(sandboxId: string): Promise<TurnCommandResult> {
    this.failIfLost(sandboxId);
    this.turnSandboxIds.push(sandboxId);
    const turn = this.scriptedTurns.shift();
    if (turn === undefined) {
      throw new Error("the test scripted no further examiner turn");
    }
    switch (turn.kind) {
      case "output":
        return { exitCode: 0, stdout: JSON.stringify(turn.output) };
      case "stdout":
        return { exitCode: 0, stdout: turn.stdout };
      case "exit":
        this.lastStderr = turn.stderr;
        return { exitCode: turn.exitCode, stdout: "" };
      case "timeout":
        throw new SandboxCommandTimeoutError(sandboxId, new Error("command timed out after 120 s"));
    }
  }

  async turnErrorTail(sandboxId: string): Promise<string> {
    this.failIfLost(sandboxId);
    return this.lastStderr;
  }

  async delete(sandboxId: string): Promise<void> {
    this.deletedSandboxIds.push(sandboxId);
  }

  uploadedNames(sandboxId: string): ExaminerFileName[] {
    return this.uploads.filter((upload) => upload.sandboxId === sandboxId).map((upload) => upload.name);
  }

  turnInputs(): unknown[] {
    return this.uploads
      .filter((upload) => upload.name === "turn.json")
      .map((upload): unknown => JSON.parse(upload.text));
  }

  private failIfLost(sandboxId: string): void {
    if (this.lostSandboxIds.has(sandboxId)) {
      throw new SandboxNotFoundError(sandboxId, new Error("sandbox was deleted"));
    }
  }
}
