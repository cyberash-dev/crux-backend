import type { WatchPageClient, WatchPageRequest, WatchPageResponse } from "../convex/watchPage/watchPageClient";

export type WatchPage = { kind: "page"; html: string; statusCode?: number };

export type WatchPageAnswer = WatchPage | { kind: "network_error"; message: string };

type RecordedRequest = Omit<WatchPageRequest, "signal">;

const CHUNK_BYTES = 16 * 1024;

export class FakeWatchPageClient implements WatchPageClient {
  readonly requests: RecordedRequest[] = [];
  readBytes = 0;
  isBodyClosed = false;

  constructor(private readonly answer: WatchPageAnswer) {}

  async get({ url, headers }: WatchPageRequest): Promise<WatchPageResponse> {
    this.requests.push({ url, headers });
    if (this.answer.kind === "network_error") {
      throw new TypeError(this.answer.message);
    }
    return { statusCode: this.answer.statusCode ?? 200, body: this.body(this.answer.html) };
  }

  private async *body(html: string): AsyncGenerator<Uint8Array> {
    const bytes = new TextEncoder().encode(html);
    try {
      for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
        const chunk = bytes.subarray(offset, offset + CHUNK_BYTES);
        this.readBytes += chunk.length;
        yield chunk;
      }
    } finally {
      this.isBodyClosed = true;
    }
  }
}
