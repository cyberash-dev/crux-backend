export class TelegramSendError extends Error {
  constructor(reason: string) {
    super(`telegram sendMessage failed: ${reason}`);
    this.name = "TelegramSendError";
  }
}
