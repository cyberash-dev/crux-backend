import { vi } from "vitest";
import { telegramOperatorChat } from "../convex/operatorChat/operatorChatFactory";
import { FakeOperatorChat } from "./FakeOperatorChat";

const TELEGRAM_CHAT_ID = "-100200300";

/* Callers must vi.mock("./operatorChat/operatorChatFactory") and call this
   after controlPlaneWithFakeClock, which leaves TELEGRAM_CHAT_ID empty. */
export function operatorChatInUse(chat: FakeOperatorChat = new FakeOperatorChat()): FakeOperatorChat {
  vi.stubEnv("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID);
  vi.mocked(telegramOperatorChat).mockReturnValue(chat);
  return chat;
}
