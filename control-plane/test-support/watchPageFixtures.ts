import type { WatchPage, WatchPageAnswer } from "./FakeWatchPageClient";

/* Filler sizes follow the live page: about 700 KB before the player
   response and 1.4 MB in total. */
const HEAD_FILLER = `<script>var ytcfg = {"filler":"${"x".repeat(700 * 1024)}"};</script>`;
const TAIL_FILLER = `<script>var ytInitialData = {"filler":"${"y".repeat(700 * 1024)}"};</script>`;

export const WATCH_PAGE_BYTES_BEFORE_STATUS = HEAD_FILLER.length;

function watchPage(playabilityStatus: string): string {
  return `<html><body>${HEAD_FILLER}<script>var ytInitialPlayerResponse = {"responseContext":{},${playabilityStatus},"videoDetails":{"videoId":"jNQXAC9IVRw"}};</script>${TAIL_FILLER}</body></html>`;
}

export function botCheckPage(): WatchPage {
  return {
    kind: "page",
    html: watchPage(
      '"playabilityStatus":{"status":"LOGIN_REQUIRED","reason":"Sign in to confirm you’re not a bot","errorScreen":{"playerErrorMessageRenderer":{}}}',
    ),
  };
}

export function okPage(): WatchPage {
  return { kind: "page", html: watchPage('"playabilityStatus":{"status":"OK","playableInEmbed":true}') };
}

export function otherLoginRequiredPage(): WatchPage {
  return {
    kind: "page",
    html: watchPage('"playabilityStatus":{"status":"LOGIN_REQUIRED","reason":"This video is private"}'),
  };
}

export function pageWithoutStatus(): WatchPage {
  return { kind: "page", html: `<html><body>${HEAD_FILLER}${TAIL_FILLER}</body></html>` };
}

export function networkError(message = "fetch failed: connect ECONNREFUSED"): WatchPageAnswer {
  return { kind: "network_error", message };
}
