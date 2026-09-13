import { v } from "convex/values";
import { internalAction } from "./_generated/server";
import { isEnvSet, requiredEnv } from "./config/env";
import { configuredMaxParallelRuns } from "./config/maxParallelRuns";
import { runSubmittedNotice } from "./model/runNotices";
import { telegramOperatorChat } from "./operatorChat/operatorChatFactory";
import { TelegramSendError } from "./operatorChat/telegramSendError";
import { redactedErrorMessage, redactedText } from "./security/secretRedaction";

const TELEGRAM_ENV_NAMES = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"] as const;

export const sendTexts = internalAction({
  args: { texts: v.array(v.string()) },
  handler: async (_ctx, { texts }): Promise<void> => {
    await sendToOperator(texts);
  },
});

/* The text is composed here rather than in createRun so that reading
   MAX_PARALLEL_RUNS can never fail a run submission. */
export const sendRunSubmitted = internalAction({
  args: {
    run_id: v.string(),
    youtube_url: v.string(),
    external_ref: v.optional(v.string()),
    queued_ahead: v.number(),
    active_runs: v.number(),
  },
  handler: async (_ctx, submittedRun): Promise<void> => {
    await sendToOperator([runSubmittedNotice(submittedRun, configuredMaxParallelRuns())]);
  },
});

/* A failed message is logged and dropped; the next message is still sent. */
async function sendToOperator(texts: readonly string[]): Promise<void> {
  const missingEnvNames = TELEGRAM_ENV_NAMES.filter((name) => !isEnvSet(name));
  if (missingEnvNames.length > 0) {
    console.warn("telegram.not_configured", { missing_env: missingEnvNames, dropped_messages: texts.length });
    return;
  }
  const chat = telegramOperatorChat(requiredEnv("TELEGRAM_BOT_TOKEN"), requiredEnv("TELEGRAM_CHAT_ID"));
  for (const text of texts) {
    try {
      await chat.send(redactedText(text));
    } catch (error) {
      if (!(error instanceof TelegramSendError)) {
        throw error;
      }
      console.error("telegram.send_failed", { message: redactedErrorMessage(error) });
    }
  }
}
