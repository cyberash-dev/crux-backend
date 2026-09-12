const YOUTUBE_HOSTS = new Set(["youtube.com", "www.youtube.com", "m.youtube.com"]);
const SHORT_LINK_HOST = "youtu.be";
const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
const VIDEO_PATH = /^\/(?:shorts|live|embed)\/([A-Za-z0-9_-]{11})\/?$/;
const SHORT_LINK_PATH = /^\/([A-Za-z0-9_-]{11})\/?$/;

export function youtubeVideoId(rawUrl: string): string | null {
  const url = httpUrl(rawUrl);
  if (url === null) {
    return null;
  }
  if (url.hostname === SHORT_LINK_HOST) {
    return SHORT_LINK_PATH.exec(url.pathname)?.[1] ?? null;
  }
  if (!YOUTUBE_HOSTS.has(url.hostname)) {
    return null;
  }
  if (url.pathname === "/watch") {
    const watchId = url.searchParams.get("v");
    return watchId !== null && VIDEO_ID.test(watchId) ? watchId : null;
  }
  return VIDEO_PATH.exec(url.pathname)?.[1] ?? null;
}

export function canonicalWatchUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

function httpUrl(rawUrl: string): URL | null {
  try {
    const url = new URL(rawUrl);
    return url.protocol === "https:" || url.protocol === "http:" ? url : null;
  } catch (error) {
    if (error instanceof TypeError) {
      return null;
    }
    throw error;
  }
}
