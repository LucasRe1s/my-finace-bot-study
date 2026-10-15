import { parseCallbackData } from "./format";
import { applyOrderAction, type Deps } from "./orders";

const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

/** Código de vínculo de 8 caracteres, sem 0/O/1/I para facilitar a digitação. */
export function generateLinkCode(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(8));
  return Array.from(bytes, (b) => CODE_ALPHABET[b % CODE_ALPHABET.length]).join("");
}

type TgUpdate = {
  message?: { chat?: { id?: number }; text?: string };
  callback_query?: { id: string; data?: string; message?: { chat?: { id?: number } } };
};

export async function handleTelegramUpdate(
  deps: Deps & { now: () => Date },
  raw: unknown,
): Promise<void> {
  const update = (raw ?? {}) as TgUpdate;

  if (update.callback_query) {
    await handleCallback(deps, update.callback_query);
    return;
  }

  const chatId = update.message?.chat?.id;
  const text = update.message?.text?.trim();
  if (chatId && text?.startsWith("/start")) {
    await handleStart(deps, chatId, text.split(/\s+/)[1]);
  }
}

async function handleStart(deps: Deps & { now: () => Date }, chatId: number, code?: string) {
  if (!code) {
    await deps.tg.sendMessage(
      chatId,
      "Para receber os pedidos, gere um código na tela de Configurações do sistema e envie aqui: /start CODIGO",
      null,
    );
    return;
  }

  const settings = await deps.repo.getSettings();
  const valid =
    settings.link_code !== null &&
    settings.link_code_expires_at !== null &&
    code.toUpperCase() === settings.link_code &&
    new Date(settings.link_code_expires_at) > deps.now();

  if (!valid) {
    await deps.tg.sendMessage(
      chatId,
      "Código inválido ou expirado. Gere um novo na tela de Configurações.",
      null,
    );
    return;
  }

  await deps.repo.saveSettings({ granja_chat_id: chatId, link_code: null, link_code_expires_at: null });
  await deps.tg.sendMessage(
    chatId,
    "Contato vinculado com sucesso. Os novos pedidos chegarão aqui.",
    null,
  );
}

async function handleCallback(deps: Deps, cb: NonNullable<TgUpdate["callback_query"]>) {
  const { granja_chat_id } = await deps.repo.getSettings();
  if (!granja_chat_id || cb.message?.chat?.id !== granja_chat_id) {
    await deps.tg.answerCallback(cb.id, "Não autorizado");
    return;
  }

  const parsed = parseCallbackData(cb.data ?? "");
  if (!parsed) {
    await deps.tg.answerCallback(cb.id, "Ação inválida");
    return;
  }

  const res = await applyOrderAction(deps, {
    orderId: parsed.orderId,
    action: parsed.action,
    actor: "granja",
    actorLabel: "granja",
  });
  await deps.tg.answerCallback(cb.id, res.message);
}
