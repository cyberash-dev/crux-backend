export function configuredProxyUrls(): string[] {
  return (process.env.PROXY_URL ?? "")
    .split(",")
    .map((proxyUrl) => proxyUrl.trim())
    .filter((proxyUrl) => proxyUrl.length > 0);
}
