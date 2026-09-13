import { describe, expect, it, vi } from "vitest";
import { TelegramOperatorChat } from "./telegramOperatorChat";
import { TelegramSendError } from "./telegramSendError";

const BOT_TOKEN = "123456789:telegram-contract-token";
const CHAT_ID = "-100200300";

function answeringFetch(status: number, body: unknown): ReturnType<typeof vi.fn<typeof fetch>> {
  return vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status }));
}

describe("TelegramOperatorChat", () => {
  /* @covers service:EXT-004 */
  it("posts chat_id and plain text as JSON to the sendMessage URL of the bot token", async () => {
    const httpFetch = answeringFetch(200, { ok: true, result: { message_id: 1 } });
    const chat = new TelegramOperatorChat(BOT_TOKEN, CHAT_ID, httpFetch);

    await chat.send("Proxy 3/5 (port 8003) is OK again");

    expect(httpFetch.mock.calls).toEqual([
      [
        `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: CHAT_ID, text: "Proxy 3/5 (port 8003) is OK again" }),
        },
      ],
    ]);
  });

  /* @covers service:EXT-004 */
  it("reports ok false as a typed failure with the description and without the token", async () => {
    const chat = new TelegramOperatorChat(
      BOT_TOKEN,
      CHAT_ID,
      answeringFetch(401, { ok: false, description: `Unauthorized for ${BOT_TOKEN}` }),
    );

    const failure = chat.send("Proxy 1/5 (port 8001) is OK again");

    await expect(failure).rejects.toThrow(
      new TelegramSendError("HTTP 401: Unauthorized for [redacted]"),
    );
  });

  /* @covers service:EXT-004 */
  it("reports a network error that echoes the sendMessage URL as a typed failure without the token", async () => {
    const httpFetch = vi.fn<typeof fetch>(async () => {
      throw new TypeError(`fetch failed: https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`);
    });
    const chat = new TelegramOperatorChat(BOT_TOKEN, CHAT_ID, httpFetch);

    const failure = chat.send("Proxy 1/5 (port 8001) is OK again");

    await expect(failure).rejects.toThrow(
      new TelegramSendError("fetch failed: https://api.telegram.org/bot[redacted]/sendMessage"),
    );
  });

  /* @covers service:EXT-004 */
  it("reports an answer without a JSON body as a typed failure", async () => {
    const httpFetch = vi.fn<typeof fetch>(async () => new Response("<html>Bad Gateway</html>", { status: 502 }));
    const chat = new TelegramOperatorChat(BOT_TOKEN, CHAT_ID, httpFetch);

    const failure = chat.send("Proxy 1/5 (port 8001) is OK again");

    await expect(failure).rejects.toThrow(new TelegramSendError("HTTP 502: no description"));
  });
});
