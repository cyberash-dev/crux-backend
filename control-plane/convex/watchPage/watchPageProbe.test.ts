import { describe, expect, it, vi } from "vitest";
import { FakeWatchPageClient, type WatchPageAnswer } from "../../test-support/FakeWatchPageClient";
import {
  botCheckPage,
  networkError,
  okPage,
  otherLoginRequiredPage,
  pageWithoutStatus,
  WATCH_PAGE_BYTES_BEFORE_STATUS,
} from "../../test-support/watchPageFixtures";
import { probedWatchPage } from "./watchPageProbe";

const PROXY_URL = "http://probe-user:probe-pass@disp.proxy.test:8003";

describe("watch page probe", () => {
  /* @covers service:EXT-005 */
  it.each<[string, WatchPageAnswer, string]>([
    ["the bot-check page", botCheckPage(), "blocked"],
    ["the OK page", okPage(), "ok"],
    ["a page without playabilityStatus", pageWithoutStatus(), "unknown"],
    ["a LOGIN_REQUIRED page with another reason", otherLoginRequiredPage(), "unknown"],
    ["a non-200 answer", { ...okPage(), statusCode: 429 }, "unknown"],
    ["a network error", networkError(), "unknown"],
  ])("classifies %s as %s", async (_name, answer, expectedStatus) => {
    const client = new FakeWatchPageClient(answer);

    const probe = await probedWatchPage(client);

    expect(probe.status).toBe(expectedStatus);
  });

  /* @covers service:EXT-005 */
  it("stops reading the body once the playability status is found", async () => {
    const client = new FakeWatchPageClient(botCheckPage());

    await probedWatchPage(client);

    expect(client.isBodyClosed).toBe(true);
    expect(client.readBytes).toBeLessThan(WATCH_PAGE_BYTES_BEFORE_STATUS + 64 * 1024);
  });

  /* @covers service:EXT-005 */
  it("sends one GET of the fixed public video with a desktop User-Agent and Accept-Language en-US", async () => {
    const client = new FakeWatchPageClient(okPage());

    await probedWatchPage(client);

    expect(client.requests).toEqual([
      {
        url: "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        headers: {
          "User-Agent": expect.stringMatching(/^Mozilla\/5\.0 \(Macintosh; .*\) .*Chrome\/\d+/),
          "Accept-Language": "en-US,en;q=0.9",
        },
      },
    ]);
  });

  /* @covers service:EXT-005 */
  it("reports a network error that echoes the proxy URL without the URL", async () => {
    vi.stubEnv("PROXY_URL", PROXY_URL);
    const client = new FakeWatchPageClient(networkError(`connect via ${PROXY_URL} failed`));

    const probe = await probedWatchPage(client);

    expect(probe).toEqual({ status: "unknown", detail: "connect via [redacted] failed" });
  });
});
