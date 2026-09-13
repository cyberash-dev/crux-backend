import { describe, expect, it, vi } from "vitest";
import { CLOCK_START, runScheduledFunctions, SENTINEL_SECRETS } from "../test-support/controlPlane";
import { FakeOperatorChat } from "../test-support/FakeOperatorChat";
import { postWorker } from "../test-support/httpCalls";
import {
  HOUR_MS,
  probeAnswering,
  proxyHealthControlPlane,
  storedProxyHealths,
} from "../test-support/proxyHealthArrangement";
import { insertActiveRun } from "../test-support/runArrangement";
import { botCheckPage, networkError, okPage, pageWithoutStatus } from "../test-support/watchPageFixtures";

vi.mock("./watchPage/watchPageClientFactory", () => ({ proxiedWatchPageClient: vi.fn() }));
vi.mock("./operatorChat/operatorChatFactory", () => ({ telegramOperatorChat: vi.fn() }));
vi.mock("./sandbox/daytonaGatewayFactory", () => ({ daytonaSandboxGateway: vi.fn() }));

const START = CLOCK_START.getTime();
const RUN_TOKEN = "proxy-health-run-token";

describe("proxy health", () => {
  /* @covers service:REQ-005 */
  it("stores the blocked, ok and unknown probe results per proxy index with their start and check times", async () => {
    const controlPlane = proxyHealthControlPlane();

    await probeAnswering(controlPlane, [botCheckPage(), okPage(), pageWithoutStatus()]);

    expect(await storedProxyHealths(controlPlane)).toEqual([
      { proxy_index: 0, status: "blocked", since: START, checked_at: START, last_known_status: "blocked" },
      { proxy_index: 1, status: "ok", since: START, checked_at: START, last_known_status: "ok" },
      { proxy_index: 2, status: "unknown", since: START, checked_at: START },
    ]);
  });

  /* @covers service:REQ-005 */
  it("marks a proxy unknown after a network error and keeps its previous status for the change check", async () => {
    const controlPlane = proxyHealthControlPlane();
    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [networkError(), okPage(), okPage()]);

    expect((await storedProxyHealths(controlPlane))[0]).toEqual({
      proxy_index: 0,
      status: "unknown",
      since: START + HOUR_MS,
      checked_at: START + HOUR_MS,
      last_known_status: "ok",
    });
  });

  /* @covers service:REQ-005 */
  it("sends one message naming the proxy index and port when an ok proxy turns blocked", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS + 30 * 60 * 1000);

    await probeAnswering(controlPlane, [okPage(), okPage(), botCheckPage()]);

    expect(chat.sentTexts).toEqual(["Proxy 3/3 (port 8003) is blocked by YouTube since 11:30 UTC"]);
  });

  /* @covers service:REQ-005 */
  it("sends no message on the first observation of an ok proxy", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);

    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual([]);
  });

  /* @covers service:REQ-005 */
  it("reports the first observation of a blocked proxy as a change from ok", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);

    await probeAnswering(controlPlane, [okPage(), botCheckPage(), okPage()]);

    expect(chat.sentTexts).toEqual(["Proxy 2/3 (port 8002) is blocked by YouTube since 10:00 UTC"]);
  });

  /* @covers service:REQ-005 */
  it("reports a blocked check after only unknown checks as a change from ok", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [networkError(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual(["Proxy 1/3 (port 8001) is blocked by YouTube since 11:00 UTC"]);
  });

  /* @covers service:REQ-005 */
  it("adds the every-proxy message when the first probe finds every proxy blocked", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);

    await probeAnswering(controlPlane, [botCheckPage(), botCheckPage(), botCheckPage()]);

    expect(chat.sentTexts).toEqual([
      "Proxy 1/3 (port 8001) is blocked by YouTube since 10:00 UTC",
      "Proxy 2/3 (port 8002) is blocked by YouTube since 10:00 UTC",
      "Proxy 3/3 (port 8003) is blocked by YouTube since 10:00 UTC",
      "All 3 proxies are blocked by YouTube; new runs fail with DOWNLOAD_BLOCKED",
    ]);
  });

  /* @covers service:REQ-005 */
  it("sends one message when a blocked proxy turns ok again", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual([
      "Proxy 1/3 (port 8001) is blocked by YouTube since 10:00 UTC",
      "Proxy 1/3 (port 8001) is OK again",
    ]);
  });

  /* @covers service:REQ-005 */
  it("sends no message when hourly probes repeat the same statuses", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);
    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual(["Proxy 1/3 (port 8001) is blocked by YouTube since 10:00 UTC"]);
  });

  /* @covers service:REQ-005 */
  it("sends no message when an ok proxy is unknown for one probe and ok again", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);
    await probeAnswering(controlPlane, [pageWithoutStatus(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual([]);
  });

  /* @covers service:REQ-005 */
  it("adds the every-proxy message when the last ok proxy turns blocked", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [botCheckPage(), botCheckPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [botCheckPage(), botCheckPage(), botCheckPage()]);

    expect(chat.sentTexts).toEqual([
      "Proxy 1/3 (port 8001) is blocked by YouTube since 10:00 UTC",
      "Proxy 2/3 (port 8002) is blocked by YouTube since 10:00 UTC",
      "Proxy 3/3 (port 8003) is blocked by YouTube since 11:00 UTC",
      "All 3 proxies are blocked by YouTube; new runs fail with DOWNLOAD_BLOCKED",
    ]);
  });

  /* @covers service:REQ-005 */
  it("marks the proxy of a DOWNLOAD_BLOCKED completion blocked at once and reports the change", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(10 * 60 * 1000);
    const runId = await insertActiveRun(controlPlane, RUN_TOKEN, "running");

    await postWorker(controlPlane, { runId, endpoint: "complete" }, RUN_TOKEN, {
      status: "failed",
      error: { code: "DOWNLOAD_BLOCKED", message: "Sign in to confirm you're not a bot" },
    });
    await runScheduledFunctions(controlPlane);

    expect({ health: (await storedProxyHealths(controlPlane))[0], sentTexts: chat.sentTexts }).toEqual({
      health: {
        proxy_index: 0,
        status: "blocked",
        since: START + 10 * 60 * 1000,
        checked_at: START + 10 * 60 * 1000,
        last_known_status: "blocked",
      },
      sentTexts: ["Proxy 1/3 (port 8001) is blocked by YouTube since 10:10 UTC"],
    });
  });

  /* @covers service:REQ-005 */
  it.each(["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])(
    "stores the status change without sending and logs a warning when %s is missing",
    async (missingEnvName) => {
      const chat = new FakeOperatorChat();
      const controlPlane = proxyHealthControlPlane(chat);
      await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
      vi.stubEnv(missingEnvName, "");
      const warningLog = vi.spyOn(console, "warn").mockImplementation(() => undefined);

      await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);

      expect({
        status: (await storedProxyHealths(controlPlane))[0]?.status,
        sentTexts: chat.sentTexts,
        warnings: warningLog.mock.calls,
      }).toEqual({
        status: "blocked",
        sentTexts: [],
        warnings: [["telegram.not_configured", { missing_env: [missingEnvName], dropped_messages: 1 }]],
      });
    },
  );

  /* @covers service:REQ-005 */
  it("logs a Telegram error that echoes the bot token without the token and keeps the status change stored", async () => {
    const chat = new FakeOperatorChat(`HTTP 401: Unauthorized for ${SENTINEL_SECRETS.TELEGRAM_BOT_TOKEN}`);
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => undefined);

    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);

    expect({ status: (await storedProxyHealths(controlPlane))[0]?.status, errors: errorLog.mock.calls }).toEqual({
      status: "blocked",
      errors: [
        ["telegram.send_failed", { message: "telegram sendMessage failed: HTTP 401: Unauthorized for [redacted]" }],
      ],
    });
  });

  /* @covers service:REQ-005 */
  it("leaves runs unchanged when a probe blocks every proxy and the message fails", async () => {
    const controlPlane = proxyHealthControlPlane(new FakeOperatorChat("HTTP 500: Internal Server Error"));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
    await insertActiveRun(controlPlane, RUN_TOKEN, "running");
    const runsBefore = await controlPlane.run(async (ctx) => ctx.db.query("runs").collect());

    await probeAnswering(controlPlane, [botCheckPage(), botCheckPage(), botCheckPage()]);

    expect(await controlPlane.run(async (ctx) => ctx.db.query("runs").collect())).toEqual(runsBefore);
  });
});
