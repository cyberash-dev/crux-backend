import { convexTest, type TestConvex } from "convex-test";
import { vi } from "vitest";
import schema from "../convex/schema";
import { modules } from "../convex/test.setup";

export type ControlPlane = TestConvex<typeof schema>;

export const SENTINEL_SECRETS = {
  DAYTONA_API_KEY: "sentinel-daytona-key-7f3a",
  PROXY_URL: "http://sentinel-proxy-user:sentinel-proxy-pass@proxy.test:3128",
  CLAUDE_CODE_OAUTH_TOKEN: "sentinel-claude-oauth-token-91c2",
  ELEVENLABS_API_KEY: "sentinel-elevenlabs-key-44d0",
  EXA_API_KEY: "sentinel-exa-key-0b8e",
  SERVICE_API_KEY: "sentinel-service-key-c61d",
  TELEGRAM_BOT_TOKEN: "123456789:sentinel-telegram-bot-token-5e7b",
} as const;

export const WORKER_SNAPSHOT = "konspekt-worker-test-snapshot";
export const WORKER_API_BASE = "https://control-plane.test";
export const CLOCK_START = new Date("2026-09-12T10:00:00.000Z");

export function controlPlaneWithFakeClock(): ControlPlane {
  vi.useFakeTimers();
  vi.setSystemTime(CLOCK_START);
  for (const [name, value] of Object.entries(SENTINEL_SECRETS)) {
    vi.stubEnv(name, value);
  }
  vi.stubEnv("WORKER_SNAPSHOT", WORKER_SNAPSHOT);
  vi.stubEnv("WORKER_API_BASE", WORKER_API_BASE);
  vi.stubEnv("TELEGRAM_CHAT_ID", "");
  return convexTest(schema, modules);
}

export async function runScheduledFunctions(controlPlane: ControlPlane): Promise<void> {
  await controlPlane.finishAllScheduledFunctions(vi.runAllTimers);
}

export function sentinelSecretsIn(text: string): string[] {
  return Object.values(SENTINEL_SECRETS).filter((secret) => text.includes(secret));
}
