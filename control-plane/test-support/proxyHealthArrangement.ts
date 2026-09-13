import { vi } from "vitest";
import { internal } from "../convex/_generated/api";
import type { Doc } from "../convex/_generated/dataModel";
import { telegramOperatorChat } from "../convex/operatorChat/operatorChatFactory";
import { proxiedWatchPageClient } from "../convex/watchPage/watchPageClientFactory";
import { type ControlPlane, controlPlaneWithFakeClock, runScheduledFunctions } from "./controlPlane";
import { FakeOperatorChat } from "./FakeOperatorChat";
import { FakeWatchPageClient, type WatchPageAnswer } from "./FakeWatchPageClient";

export const HEALTH_PROXY_URLS = [
  "http://health-user-a:health-pass-a@disp.proxy.test:8001",
  "http://health-user-b:health-pass-b@disp.proxy.test:8002",
  "http://health-user-c:health-pass-c@disp.proxy.test:8003",
] as const;
export const TELEGRAM_CHAT_ID = "-100200300";
export const HOUR_MS = 60 * 60 * 1000;

type StoredProxyHealth = Omit<Doc<"proxy_health">, "_id" | "_creationTime">;

/* Callers must vi.mock("./watchPage/watchPageClientFactory") and
   vi.mock("./operatorChat/operatorChatFactory"). */
export function proxyHealthControlPlane(chat: FakeOperatorChat = new FakeOperatorChat()): ControlPlane {
  const controlPlane = controlPlaneWithFakeClock();
  vi.stubEnv("PROXY_URL", HEALTH_PROXY_URLS.join(","));
  vi.stubEnv("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID);
  vi.mocked(telegramOperatorChat).mockReturnValue(chat);
  return controlPlane;
}

export async function probeAnswering(
  controlPlane: ControlPlane,
  answers: readonly WatchPageAnswer[],
): Promise<FakeWatchPageClient[]> {
  const clients = answers.map((answer) => new FakeWatchPageClient(answer));
  vi.mocked(proxiedWatchPageClient).mockImplementation((proxyUrl) => {
    const client = clients[HEALTH_PROXY_URLS.findIndex((listedUrl) => listedUrl === proxyUrl)];
    if (client === undefined) {
      throw new Error(`the test scripted no watch page for ${proxyUrl}`);
    }
    return client;
  });
  await controlPlane.action(internal.proxyProbe.probeProxies, {});
  await runScheduledFunctions(controlPlane);
  return clients;
}

export async function storedProxyHealths(controlPlane: ControlPlane): Promise<StoredProxyHealth[]> {
  const healths = await controlPlane.run(async (ctx) => ctx.db.query("proxy_health").collect());
  return healths
    .map(({ _id, _creationTime, ...health }) => health)
    .sort((left, right) => left.proxy_index - right.proxy_index);
}
