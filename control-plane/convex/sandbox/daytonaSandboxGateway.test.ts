/** @vitest-environment node */
import {
  type CreateSandboxFromSnapshotParams,
  DaytonaNotFoundError,
  DaytonaProcessExecutionTimeoutError,
} from "@daytona/sdk";
import { describe, expect, it } from "vitest";
import {
  type DaytonaExaminerClient,
  type DaytonaExaminerSandbox,
  DaytonaExaminerGateway,
} from "./daytonaExaminerGateway";
import { type DaytonaClient, type DaytonaSandbox, DaytonaSandboxGateway } from "./daytonaSandboxGateway";
import type { ExaminerSandboxSpec } from "./examinerGateway";
import type { SandboxSpec } from "./sandboxGateway";

type SessionCommand = { sessionId: string; command: string; runAsync: boolean };

class FakeDaytonaClient implements DaytonaClient {
  readonly createParams: CreateSandboxFromSnapshotParams[] = [];
  readonly createdSessionIds: string[] = [];
  readonly sessionCommands: SessionCommand[] = [];
  readonly deletedSandboxIds: string[] = [];

  constructor(private readonly createError: Error | null = null) {}

  async create(params: CreateSandboxFromSnapshotParams): Promise<DaytonaSandbox> {
    if (this.createError !== null) {
      throw this.createError;
    }
    this.createParams.push(params);
    return this.sandbox("daytona-sandbox-1");
  }

  async get(sandboxId: string): Promise<DaytonaSandbox> {
    return this.sandbox(sandboxId);
  }

  private sandbox(id: string): DaytonaSandbox {
    return {
      id,
      process: {
        createSession: async (sessionId) => {
          this.createdSessionIds.push(sessionId);
        },
        executeSessionCommand: async (sessionId, request) => {
          this.sessionCommands.push({ sessionId, ...request });
          return { cmdId: "command-1" };
        },
      },
      delete: async () => {
        this.deletedSandboxIds.push(id);
      },
    };
  }
}

function workerSandboxSpec(): SandboxSpec {
  return {
    snapshot: "konspekt-worker-snapshot",
    outboundProxyUrl: "http://proxy.test:3128",
    envVars: { KONSPEKT_RUN_ID: "run-1", CLAUDE_CODE_OAUTH_TOKEN: "claude-token" },
    labels: { run_id: "run-1" },
  };
}

describe("DaytonaSandboxGateway", () => {
  /* @covers service:EXT-001 */
  it("creates the sandbox from the snapshot with proxy, env, auto-stop off, 240 min TTL and run label", async () => {
    const client = new FakeDaytonaClient();
    const gateway = new DaytonaSandboxGateway(client);

    const sandboxId = await gateway.create(workerSandboxSpec());

    expect(sandboxId).toBe("daytona-sandbox-1");
    expect(client.createParams).toEqual([
      {
        snapshot: "konspekt-worker-snapshot",
        outboundProxyUrl: "http://proxy.test:3128",
        envVars: { KONSPEKT_RUN_ID: "run-1", CLAUDE_CODE_OAUTH_TOKEN: "claude-token" },
        labels: { run_id: "run-1" },
        autoStopInterval: 0,
        ttlMinutes: 240,
      },
    ]);
  });

  /* @covers service:EXT-001 */
  it("starts konspekt-worker asynchronously in its own session", async () => {
    const client = new FakeDaytonaClient();
    const gateway = new DaytonaSandboxGateway(client);

    await gateway.startWorker("daytona-sandbox-1");

    expect(client.createdSessionIds).toEqual(["konspekt-worker"]);
    expect(client.sessionCommands).toEqual([
      {
        sessionId: "konspekt-worker",
        command: "konspekt-worker > /root/worker.log 2>&1",
        runAsync: true,
      },
    ]);
  });

  /* @covers service:EXT-001 */
  it("surfaces a failed create as a SandboxGatewayError of the create operation", async () => {
    const gateway = new DaytonaSandboxGateway(new FakeDaytonaClient(new Error("snapshot not found")));

    const creation = gateway.create(workerSandboxSpec());

    await expect(creation).rejects.toMatchObject({
      name: "SandboxGatewayError",
      operation: "create",
      message: "sandbox create failed: snapshot not found",
    });
  });

  /* @covers service:EXT-001 */
  it("deletes the sandbox by its id", async () => {
    const client = new FakeDaytonaClient();
    const gateway = new DaytonaSandboxGateway(client);

    await gateway.delete("daytona-sandbox-7");

    expect(client.deletedSandboxIds).toEqual(["daytona-sandbox-7"]);
  });
});

type ExecutedCommand = {
  sandboxId: string;
  command: string;
  cwd: string | undefined;
  env: Record<string, string> | undefined;
  timeout: number | undefined;
};

type ClientFailure = { operation: "create" | "get" | "execute"; error: Error };

class FakeDaytonaExaminerClient implements DaytonaExaminerClient {
  readonly createParams: CreateSandboxFromSnapshotParams[] = [];
  readonly uploadedFiles: { sandboxId: string; path: string; text: string }[] = [];
  readonly commands: ExecutedCommand[] = [];
  readonly deletedSandboxIds: string[] = [];

  constructor(
    private readonly failure: ClientFailure | null = null,
    private readonly commandResult = { exitCode: 0, result: "{\"kind\":\"turn\"}" },
  ) {}

  async create(params: CreateSandboxFromSnapshotParams): Promise<DaytonaExaminerSandbox> {
    this.failIf("create");
    this.createParams.push(params);
    return this.sandbox("daytona-examiner-1");
  }

  async get(sandboxId: string): Promise<DaytonaExaminerSandbox> {
    this.failIf("get");
    return this.sandbox(sandboxId);
  }

  private sandbox(id: string): DaytonaExaminerSandbox {
    return {
      id,
      fs: {
        uploadFile: async (file, remotePath) => {
          this.uploadedFiles.push({ sandboxId: id, path: remotePath, text: file.toString("utf8") });
        },
      },
      process: {
        executeCommand: async (command, cwd, env, timeout) => {
          this.failIf("execute");
          this.commands.push({ sandboxId: id, command, cwd, env, timeout });
          return this.commandResult;
        },
      },
      delete: async () => {
        this.deletedSandboxIds.push(id);
      },
    };
  }

  private failIf(operation: ClientFailure["operation"]): void {
    if (this.failure?.operation === operation) {
      throw this.failure.error;
    }
  }
}

function examinerSandboxSpec(): ExaminerSandboxSpec {
  return {
    snapshot: "konspekt-examiner-snapshot",
    envVars: { CLAUDE_CODE_OAUTH_TOKEN: "claude-token", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1" },
    labels: { exam_id: "exam-1" },
  };
}

function missingSandbox(): ClientFailure {
  return { operation: "get", error: new DaytonaNotFoundError("Sandbox with ID daytona-examiner-9 not found", 404) };
}

/* @covers service:DLT-004 */
describe("DaytonaExaminerGateway", () => {
  /* @covers service:EXT-001 */
  it("creates an ephemeral sandbox from the examiner snapshot with 15 min auto-stop, its env, the exam label and no proxy", async () => {
    const client = new FakeDaytonaExaminerClient();
    const gateway = new DaytonaExaminerGateway(client);

    const sandboxId = await gateway.create(examinerSandboxSpec());

    expect(sandboxId).toBe("daytona-examiner-1");
    expect(client.createParams).toEqual([
      {
        snapshot: "konspekt-examiner-snapshot",
        envVars: { CLAUDE_CODE_OAUTH_TOKEN: "claude-token", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1" },
        labels: { exam_id: "exam-1" },
        ephemeral: true,
        autoStopInterval: 15,
      },
    ]);
  });

  /* @covers service:EXT-001 */
  it("surfaces a failed create as a SandboxGatewayError of the create operation", async () => {
    const gateway = new DaytonaExaminerGateway(
      new FakeDaytonaExaminerClient({ operation: "create", error: new Error("snapshot not found") }),
    );

    const creation = gateway.create(examinerSandboxSpec());

    await expect(creation).rejects.toMatchObject({
      name: "SandboxGatewayError",
      operation: "create",
      message: "sandbox create failed: snapshot not found",
    });
  });

  /* @covers service:EXT-001 */
  it("uploads a file into the exam materials directory", async () => {
    const client = new FakeDaytonaExaminerClient();
    const gateway = new DaytonaExaminerGateway(client);

    await gateway.upload("daytona-examiner-1", { name: "turn.json", content: new TextEncoder().encode("{\"kind\":\"open\"}") });

    expect(client.uploadedFiles).toEqual([
      { sandboxId: "daytona-examiner-1", path: "/root/exam/turn.json", text: "{\"kind\":\"open\"}" },
    ]);
  });

  /* @covers service:EXT-001 */
  it("runs konspekt-exam-turn synchronously with a 120 s timeout and stderr kept out of stdout", async () => {
    const client = new FakeDaytonaExaminerClient();
    const gateway = new DaytonaExaminerGateway(client);

    await gateway.runTurn("daytona-examiner-1");

    expect(client.commands).toEqual([
      {
        sandboxId: "daytona-examiner-1",
        command: "sh -c 'konspekt-exam-turn /root/exam 2>/root/exam/turn.err'",
        cwd: undefined,
        env: undefined,
        timeout: 120,
      },
    ]);
  });

  /* @covers service:EXT-001 */
  it("returns the exit code and stdout of the turn command", async () => {
    const gateway = new DaytonaExaminerGateway(
      new FakeDaytonaExaminerClient(null, { exitCode: 2, result: "" }),
    );

    const result = await gateway.runTurn("daytona-examiner-1");

    expect(result).toEqual({ exitCode: 2, stdout: "" });
  });

  /* @covers service:EXT-001 */
  it("reads the tail of the turn's stderr file", async () => {
    const client = new FakeDaytonaExaminerClient(null, { exitCode: 0, result: "quiz.json missing" });
    const gateway = new DaytonaExaminerGateway(client);

    const tail = await gateway.turnErrorTail("daytona-examiner-1");

    expect(tail).toBe("quiz.json missing");
    expect(client.commands).toMatchObject([{ command: "tail -c 2000 /root/exam/turn.err" }]);
  });

  /* @covers service:EXT-001 */
  it("surfaces a turn over its timeout as SandboxCommandTimeoutError", async () => {
    const timeout = new DaytonaProcessExecutionTimeoutError("execution timed out", 408, undefined, "PROCESS_EXECUTION_TIMEOUT");
    const gateway = new DaytonaExaminerGateway(new FakeDaytonaExaminerClient({ operation: "execute", error: timeout }));

    const turn = gateway.runTurn("daytona-examiner-1");

    await expect(turn).rejects.toMatchObject({ name: "SandboxCommandTimeoutError", sandboxId: "daytona-examiner-1" });
  });

  /* @covers service:EXT-001 */
  it("surfaces a missing sandbox on upload as SandboxNotFoundError", async () => {
    const gateway = new DaytonaExaminerGateway(new FakeDaytonaExaminerClient(missingSandbox()));

    const upload = gateway.upload("daytona-examiner-9", { name: "turn.json", content: new Uint8Array() });

    await expect(upload).rejects.toMatchObject({ name: "SandboxNotFoundError", sandboxId: "daytona-examiner-9" });
  });

  /* @covers service:EXT-001 */
  it("surfaces a missing sandbox on the turn command as SandboxNotFoundError", async () => {
    const gateway = new DaytonaExaminerGateway(new FakeDaytonaExaminerClient(missingSandbox()));

    const turn = gateway.runTurn("daytona-examiner-9");

    await expect(turn).rejects.toMatchObject({ name: "SandboxNotFoundError", sandboxId: "daytona-examiner-9" });
  });

  /* @covers service:EXT-001 */
  it("surfaces any other upload failure as a SandboxGatewayError of the upload operation", async () => {
    const gateway = new DaytonaExaminerGateway(
      new FakeDaytonaExaminerClient({ operation: "get", error: new Error("toolbox unavailable") }),
    );

    const upload = gateway.upload("daytona-examiner-1", { name: "quiz.json", content: new Uint8Array() });

    await expect(upload).rejects.toMatchObject({ name: "SandboxGatewayError", operation: "upload" });
  });

  /* @covers service:EXT-001 */
  it("deletes the examiner sandbox by its id", async () => {
    const client = new FakeDaytonaExaminerClient();
    const gateway = new DaytonaExaminerGateway(client);

    await gateway.delete("daytona-examiner-7");

    expect(client.deletedSandboxIds).toEqual(["daytona-examiner-7"]);
  });
});
