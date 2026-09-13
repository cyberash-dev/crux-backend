import type { OperatorChat } from "../convex/operatorChat/operatorChat";
import { TelegramSendError } from "../convex/operatorChat/telegramSendError";

export class FakeOperatorChat implements OperatorChat {
  readonly sentTexts: string[] = [];

  constructor(private readonly failure: string | null = null) {}

  async send(text: string): Promise<void> {
    if (this.failure !== null) {
      throw new TelegramSendError(this.failure);
    }
    this.sentTexts.push(text);
  }
}
