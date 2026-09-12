export type ExaminerSandboxSpec = {
  snapshot: string;
  envVars: Record<string, string>;
  labels: Record<string, string>;
};

export type ExaminerFileName = "konspekt.md" | "quiz.json" | "turn.json";

export type ExaminerFile = { name: ExaminerFileName; content: Uint8Array };

export type TurnCommandResult = { exitCode: number; stdout: string };

/* upload, runTurn and turnErrorTail throw SandboxNotFoundError once the
   sandbox is gone; runTurn throws SandboxCommandTimeoutError after 120 s. */
export interface ExaminerGateway {
  create(spec: ExaminerSandboxSpec): Promise<string>;
  upload(sandboxId: string, file: ExaminerFile): Promise<void>;
  runTurn(sandboxId: string): Promise<TurnCommandResult>;
  turnErrorTail(sandboxId: string): Promise<string>;
  delete(sandboxId: string): Promise<void>;
}
