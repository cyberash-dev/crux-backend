import type { KnownProxyHealthStatus } from "../model/proxyHealthVocabulary";
import { redactedErrorMessage } from "../security/secretRedaction";
import type { WatchPageClient } from "./watchPageClient";

const PROBE_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw";
const PROBE_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
  "Accept-Language": "en-US,en;q=0.9",
} as const;

const PROBE_TIMEOUT_MS = 30_000;
const PLAYABILITY_KEY = '"playabilityStatus":{';
/* The status and its reason follow the key within a few hundred characters,
   so reading stops this far past the key instead of at the end of the page. */
const PLAYABILITY_WINDOW_CHARS = 1024;
const PLAYABILITY_PATTERN = /^"playabilityStatus":\{"status":"([A-Z_]+)"(?:,"reason":"((?:[^"\\]|\\.)*)")?/;
const BOT_CHECK_REASON_PATTERN = /not\s+a\s+bot/i;

export type WatchPageProbe = { status: KnownProxyHealthStatus } | { status: "unknown"; detail: string };

export async function probedWatchPage(client: WatchPageClient): Promise<WatchPageProbe> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const response = await client.get({ url: PROBE_VIDEO_URL, headers: PROBE_HEADERS, signal: controller.signal });
    if (response.statusCode !== 200) {
      return { status: "unknown", detail: `HTTP ${response.statusCode}` };
    }
    return playabilityProbe(await playabilityText(response.body));
  } catch (error) {
    return { status: "unknown", detail: redactedErrorMessage(error) };
  } finally {
    clearTimeout(timeout);
    controller.abort();
  }
}

async function playabilityText(body: AsyncIterable<Uint8Array>): Promise<string | null> {
  const decoder = new TextDecoder();
  let page = "";
  let keyIndex = -1;
  for await (const chunk of body) {
    const searchFrom = Math.max(0, page.length - PLAYABILITY_KEY.length);
    page += decoder.decode(chunk, { stream: true });
    keyIndex = keyIndex >= 0 ? keyIndex : page.indexOf(PLAYABILITY_KEY, searchFrom);
    if (keyIndex >= 0 && page.length - keyIndex >= PLAYABILITY_WINDOW_CHARS) {
      break;
    }
  }
  return keyIndex >= 0 ? page.slice(keyIndex, keyIndex + PLAYABILITY_WINDOW_CHARS) : null;
}

function playabilityProbe(playability: string | null): WatchPageProbe {
  const match = playability?.match(PLAYABILITY_PATTERN) ?? null;
  if (match === null) {
    return { status: "unknown", detail: "no playability status" };
  }
  const [, playabilityStatus, reason = ""] = match;
  if (playabilityStatus === "OK") {
    return { status: "ok" };
  }
  if (playabilityStatus === "LOGIN_REQUIRED" && BOT_CHECK_REASON_PATTERN.test(reason)) {
    return { status: "blocked" };
  }
  return { status: "unknown", detail: `playability status ${playabilityStatus ?? "missing"}` };
}
