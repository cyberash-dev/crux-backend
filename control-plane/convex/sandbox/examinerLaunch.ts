import { isEnvSet, MissingEnvError, requiredEnv } from "../config/env";
import type { ExaminerSandboxSpec } from "./examinerGateway";

const EXAMINER_LAUNCH_ENV_NAMES = [
  "DAYTONA_API_KEY",
  "EXAMINER_SNAPSHOT",
  "CLAUDE_CODE_OAUTH_TOKEN",
] as const;

export type ExaminerLaunchConfig = {
  daytonaApiKey: string;
  snapshot: string;
  claudeCodeOauthToken: string;
};

export function examinerLaunchConfig(): ExaminerLaunchConfig {
  const missingNames = EXAMINER_LAUNCH_ENV_NAMES.filter((name) => !isEnvSet(name));
  if (missingNames.length > 0) {
    throw new MissingEnvError(missingNames);
  }
  return {
    daytonaApiKey: requiredEnv("DAYTONA_API_KEY"),
    snapshot: requiredEnv("EXAMINER_SNAPSHOT"),
    claudeCodeOauthToken: requiredEnv("CLAUDE_CODE_OAUTH_TOKEN"),
  };
}

export function examinerSandboxSpec(config: ExaminerLaunchConfig, examId: string): ExaminerSandboxSpec {
  return {
    snapshot: config.snapshot,
    labels: { exam_id: examId },
    envVars: {
      CLAUDE_CODE_OAUTH_TOKEN: config.claudeCodeOauthToken,
      CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1",
    },
  };
}
