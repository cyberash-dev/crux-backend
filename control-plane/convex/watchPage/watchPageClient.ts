export type WatchPageRequest = {
  url: string;
  headers: Readonly<Record<string, string>>;
  signal: AbortSignal;
};

export type WatchPageResponse = {
  statusCode: number;
  body: AsyncIterable<Uint8Array>;
};

export interface WatchPageClient {
  get(request: WatchPageRequest): Promise<WatchPageResponse>;
}
