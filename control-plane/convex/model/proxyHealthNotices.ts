export function proxySummaryNotice(proxyCount: number, blockedProxyUrls: readonly string[]): string {
  const okCount = proxyCount - blockedProxyUrls.length;
  const summary = `Proxies: ${okCount}/${proxyCount} OK.`;
  if (blockedProxyUrls.length === 0) {
    return summary;
  }
  const blockedPorts = blockedProxyUrls.map((proxyUrl) => `port ${portOf(proxyUrl)}`).join(", ");
  const consequence = okCount === 0 ? " New runs fail with DOWNLOAD_BLOCKED." : "";
  return `${summary} Blocked: ${blockedPorts}.${consequence}`;
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
