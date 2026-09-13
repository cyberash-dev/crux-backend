"use node";

import { UndiciWatchPageClient } from "./undiciWatchPageClient";
import type { WatchPageClient } from "./watchPageClient";

export function proxiedWatchPageClient(proxyUrl: string): WatchPageClient {
  return new UndiciWatchPageClient(proxyUrl);
}
