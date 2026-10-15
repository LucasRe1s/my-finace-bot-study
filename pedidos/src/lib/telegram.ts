import type { InlineKeyboard } from "./types";

export interface TelegramClient {
  /** Envia mensagem e devolve o message_id. */
  sendMessage(chatId: number, text: string, keyboard: InlineKeyboard | null): Promise<number>;
  /** Edita texto e botões; keyboard null remove os botões. */
  editMessage(
    chatId: number,
    messageId: number,
    text: string,
    keyboard: InlineKeyboard | null,
  ): Promise<void>;
  answerCallback(callbackQueryId: string, text?: string): Promise<void>;
}

export function createTelegramClient(token: string): TelegramClient {
  async function call<T>(method: string, body: Record<string, unknown>): Promise<T> {
    const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = (await res.json()) as { ok: boolean; result: T; description?: string };
    if (!json.ok) {
      throw new Error(`Telegram ${method}: ${json.description ?? res.status}`);
    }
    return json.result;
  }

  return {
    async sendMessage(chatId, text, keyboard) {
      const msg = await call<{ message_id: number }>("sendMessage", {
        chat_id: chatId,
        text,
        ...(keyboard ? { reply_markup: { inline_keyboard: keyboard } } : {}),
      });
      return msg.message_id;
    },
    async editMessage(chatId, messageId, text, keyboard) {
      await call("editMessageText", {
        chat_id: chatId,
        message_id: messageId,
        text,
        reply_markup: { inline_keyboard: keyboard ?? [] },
      });
    },
    async answerCallback(callbackQueryId, text) {
      await call("answerCallbackQuery", {
        callback_query_id: callbackQueryId,
        ...(text ? { text } : {}),
      });
    },
  };
}
