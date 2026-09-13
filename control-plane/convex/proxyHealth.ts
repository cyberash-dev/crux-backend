import { v } from "convex/values";
import { internalAction, internalMutation } from "./_generated/server";
import { isEnvSet, requiredEnv } from "./config/env";
import { recordProxyChecks } from "./model/proxyHealthRecord";
import { proxyCheckValidator } from "./model/proxyHealthVocabulary";
import { telegramOperatorChat } from "./operatorChat/operatorChatFactory";
import { TelegramSendError } from "./operatorChat/telegramSendError";
import { redactedErrorMessage } from "./security/secretRedaction";

const TELEGRAM_ENV_NAMES = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"] as const;

export const recordProbeChecks = internalMutation({
  args: { checks: v.array(proxyCheckValidator) },
  handler: async (ctx, { checks }): Promise<void> => {
    await recordProxyChecks(ctx, checks);
  },
});

/* A failed message is logged and dropped; the next message is still sent. */
export const sendNotices = internalAction({
  args: { texts: v.array(v.string()) },
  handler: async (_ctx, { texts }): Promise<void> => {
    const missingEnvNames = TELEGRAM_ENV_NAMES.filter((name) => !isEnvSet(name));
    if (missingEnvNames.length > 0) {
      console.warn("telegram.not_configured", { missing_env: missingEnvNames, dropped_messages: texts.length });
      return;
    }
    const chat = telegramOperatorChat(requiredEnv("TELEGRAM_BOT_TOKEN"), requiredEnv("TELEGRAM_CHAT_ID"));
    for (const text of texts) {
      try {
        await chat.send(text);
      } catch (error) {
        if (!(error instanceof TelegramSendError)) {
          throw error;
        }
        console.error("telegram.send_failed", { message: redactedErrorMessage(error) });
      }
    }
  },
});
