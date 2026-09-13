import { isJsonObject, parsedJson } from "../httpBoundary/jsonBody";
import { redactedErrorMessage, redactedText } from "../security/secretRedaction";
import type { OperatorChat } from "./operatorChat";
import { TelegramSendError } from "./telegramSendError";

export class TelegramOperatorChat implements OperatorChat {
  constructor(
    private readonly botToken: string,
    private readonly chatId: string,
    private readonly httpFetch: typeof fetch,
  ) {}

  async send(text: string): Promise<void> {
    const response = await this.posted(text);
    const answer = parsedJson(await response.text());
    const answerBody = answer.kind === "parsed" && isJsonObject(answer.value) ? answer.value : null;
    if (answerBody?.ok === true) {
      return;
    }
    const description =
      typeof answerBody?.description === "string" ? answerBody.description : "no description";
    throw new TelegramSendError(redactedText(`HTTP ${response.status}: ${description}`, [this.botToken]));
  }

  private async posted(text: string): Promise<Response> {
    try {
      return await this.httpFetch(`https://api.telegram.org/bot${this.botToken}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: this.chatId, text }),
      });
    } catch (error) {
      throw new TelegramSendError(redactedErrorMessage(error, [this.botToken]));
    }
  }
}
