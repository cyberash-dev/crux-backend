import type { KnownProxyHealthStatus } from "./proxyHealthVocabulary";

export type ProxyPosition = { proxyIndex: number; proxyCount: number; proxyUrl: string };

export function proxyStatusNotice(
  position: ProxyPosition,
  status: KnownProxyHealthStatus,
  since: number,
): string {
  const proxy = `Proxy ${position.proxyIndex + 1}/${position.proxyCount} (port ${portOf(position.proxyUrl)})`;
  return status === "blocked"
    ? `${proxy} is blocked by YouTube since ${new Date(since).toISOString().slice(11, 16)} UTC`
    : `${proxy} is OK again`;
}

export function everyProxyBlockedNotice(proxyCount: number): string {
  const proxies = proxyCount === 1 ? "The only proxy is" : `All ${proxyCount} proxies are`;
  return `${proxies} blocked by YouTube; new runs fail with DOWNLOAD_BLOCKED`;
}

/* A malformed PROXY_URL entry must not fail the mutation that records a
   blocked run, so its port is named unknown instead of thrown. */
function portOf(proxyUrl: string): string {
  try {
    const url = new URL(proxyUrl);
    return url.port !== "" ? url.port : url.protocol === "https:" ? "443" : "80";
  } catch {
    return "unknown";
  }
}
