"use node";

import { ProxyAgent, request } from "undici";
import type { WatchPageClient, WatchPageRequest, WatchPageResponse } from "./watchPageClient";

/* The agent is built per request so that a malformed proxy URL fails the
   request, which the probe reports as unknown, not the client creation. */
export class UndiciWatchPageClient implements WatchPageClient {
  constructor(private readonly proxyUrl: string) {}

  async get({ url, headers, signal }: WatchPageRequest): Promise<WatchPageResponse> {
    const dispatcher = new ProxyAgent(this.proxyUrl);
    const response = await request(url, { method: "GET", headers, signal, dispatcher });
    return { statusCode: response.statusCode, body: response.body };
  }
}
