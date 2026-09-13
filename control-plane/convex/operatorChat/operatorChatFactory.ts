import type { OperatorChat } from "./operatorChat";
import { TelegramOperatorChat } from "./telegramOperatorChat";

export function telegramOperatorChat(botToken: string, chatId: string): OperatorChat {
  return new TelegramOperatorChat(botToken, chatId, fetch);
}
