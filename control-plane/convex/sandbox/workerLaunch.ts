import type { Id } from "../_generated/dataModel";
import { isEnvSet, MissingEnvError, requiredEnv } from "../config/env";
import { configuredProxyUrls } from "../config/proxyUrls";
import type { RunLang } from "../model/runVocabulary";
import type { SandboxSpec } from "./sandboxGateway";

const WORKER_LAUNCH_ENV_NAMES = [
  "DAYTONA_API_KEY",
  "WORKER_SNAPSHOT",
  "PROXY_URL",
  "WORKER_API_BASE",
  "CLAUDE_CODE_OAUTH_TOKEN",
  "ELEVENLABS_API_KEY",
  "EXA_API_KEY",
] as const;

export type WorkerLaunchConfig = {
  daytonaApiKey: string;
  snapshot: string;
  proxyUrls: readonly string[];
  apiBase: string;
  claudeCodeOauthToken: string;
  elevenlabsApiKey: string;
  exaApiKey: string;
};

export type WorkerLaunch = {
  runId: Id<"runs">;
  runToken: string;
  youtubeUrl: string;
  lang: RunLang;
  proxyIndex: number | null;
};

export function workerLaunchConfig(): WorkerLaunchConfig {
  const missingNames = WORKER_LAUNCH_ENV_NAMES.filter((name) => !isEnvSet(name));
  if (missingNames.length > 0) {
    throw new MissingEnvError(missingNames);
  }
  const proxyUrls = configuredProxyUrls();
  if (proxyUrls.length === 0) {
    throw new MissingEnvError(["PROXY_URL"]);
  }
  return {
    daytonaApiKey: requiredEnv("DAYTONA_API_KEY"),
    snapshot: requiredEnv("WORKER_SNAPSHOT"),
    proxyUrls,
    apiBase: requiredEnv("WORKER_API_BASE"),
    claudeCodeOauthToken: requiredEnv("CLAUDE_CODE_OAUTH_TOKEN"),
    elevenlabsApiKey: requiredEnv("ELEVENLABS_API_KEY"),
    exaApiKey: requiredEnv("EXA_API_KEY"),
  };
}

export function sandboxSpec(config: WorkerLaunchConfig, launch: WorkerLaunch): SandboxSpec {
  return {
    snapshot: config.snapshot,
    outboundProxyUrl: proxyUrlOfIndex(config.proxyUrls, launch.proxyIndex),
    labels: { run_id: launch.runId },
    envVars: {
      KONSPEKT_RUN_ID: launch.runId,
      KONSPEKT_API_BASE: config.apiBase,
      KONSPEKT_RUN_TOKEN: launch.runToken,
      KONSPEKT_YOUTUBE_URL: launch.youtubeUrl,
      KONSPEKT_LANG: launch.lang,
      CLAUDE_CODE_OAUTH_TOKEN: config.claudeCodeOauthToken,
      ELEVENLABS_API_KEY: config.elevenlabsApiKey,
      EXA_API_KEY: config.exaApiKey,
    },
  };
}

function proxyUrlOfIndex(proxyUrls: readonly string[], proxyIndex: number | null): string {
  const proxyUrl = proxyIndex === null ? undefined : proxyUrls[proxyIndex];
  if (proxyUrl === undefined) {
    throw new MissingEnvError(["PROXY_URL"]);
  }
  return proxyUrl;
}
