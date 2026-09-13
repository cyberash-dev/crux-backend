import { describe, expect, it, vi } from "vitest";
import { CLOCK_START, runScheduledFunctions, SENTINEL_SECRETS } from "../test-support/controlPlane";
import { FakeOperatorChat } from "../test-support/FakeOperatorChat";
import { fakeGatewayInUse } from "../test-support/fakeGatewayInUse";
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
  /* @covers service:DLT-013 */
  it("sends one summary with the ok count and the blocked ports when a proxy turns blocked", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [okPage(), okPage(), botCheckPage()]);

    expect(chat.sentTexts).toEqual(["Proxies: 2/3 OK. Blocked: port 8003."]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("sends one summary when one probe changes several proxies", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [okPage(), botCheckPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [botCheckPage(), okPage(), botCheckPage()]);

    expect(chat.sentTexts).toEqual([
      "Proxies: 2/3 OK. Blocked: port 8002.",
      "Proxies: 1/3 OK. Blocked: port 8001, port 8003.",
    ]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("sends no summary on the first observation of ok proxies", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);

    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual([]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("counts a proxy without a stored status as ok, so its first blocked check changes the set", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);

    await probeAnswering(controlPlane, [okPage(), botCheckPage(), okPage()]);

    expect(chat.sentTexts).toEqual(["Proxies: 2/3 OK. Blocked: port 8002."]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("counts a proxy with only unknown checks as ok, so its first blocked check changes the set", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [networkError(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual(["Proxies: 2/3 OK. Blocked: port 8001."]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("reads 0 of N with every port when the first probe finds every proxy blocked", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);

    await probeAnswering(controlPlane, [botCheckPage(), botCheckPage(), botCheckPage()]);

    expect(chat.sentTexts).toEqual([
      "Proxies: 0/3 OK. Blocked: port 8001, port 8002, port 8003. New runs fail with DOWNLOAD_BLOCKED.",
    ]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("reads 0 of N when the last ok proxy turns blocked", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [botCheckPage(), botCheckPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [botCheckPage(), botCheckPage(), botCheckPage()]);

    expect(chat.sentTexts).toEqual([
      "Proxies: 1/3 OK. Blocked: port 8001, port 8002.",
      "Proxies: 0/3 OK. Blocked: port 8001, port 8002, port 8003. New runs fail with DOWNLOAD_BLOCKED.",
    ]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("sends a summary without blocked ports when the last blocked proxy turns ok", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [okPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual(["Proxies: 2/3 OK. Blocked: port 8001.", "Proxies: 3/3 OK."]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("sends no summary when hourly probes repeat the same blocked set", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);
    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);
    vi.advanceTimersByTime(HOUR_MS);

    await probeAnswering(controlPlane, [botCheckPage(), okPage(), okPage()]);

    expect(chat.sentTexts).toEqual(["Proxies: 2/3 OK. Blocked: port 8001."]);
  });

  /* @covers service:REQ-005 */
  /* @covers service:DLT-013 */
  it("sends no summary when an ok proxy is unknown for one probe and ok again", async () => {
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
  /* @covers service:DLT-013 */
  it("marks the proxy of a DOWNLOAD_BLOCKED completion blocked at once and sends the changed summary", async () => {
    const chat = new FakeOperatorChat();
    const controlPlane = proxyHealthControlPlane(chat);
    fakeGatewayInUse();
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
      sentTexts: ["Proxies: 2/3 OK. Blocked: port 8001."],
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
