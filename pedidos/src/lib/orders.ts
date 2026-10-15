import { formatOrderMessage, keyboardFor } from "./format";
import type { NewOrderInput, Repo } from "./repo";
import { STATUS_LABEL, nextStatus } from "./status";
import type { TelegramClient } from "./telegram";
import type { Actor, OrderAction } from "./types";

export type Deps = { repo: Repo; tg: TelegramClient };

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function validate(input: NewOrderInput): string | null {
  if (!input.customer_name.trim()) return "Informe o nome do mercado";
  if (!input.items.length) return "Adicione pelo menos um item";
  if (input.items.some((i) => !Number.isInteger(i.boxes) || i.boxes <= 0)) {
    return "Quantidade de caixas inválida";
  }
  return null;
}

export async function createOrder(
  deps: Deps,
  input: NewOrderInput,
): Promise<{ ok: false; error: string } | { ok: true; id: string; sent: boolean; error?: string }> {
  const invalid = validate(input);
  if (invalid) return { ok: false, error: invalid };

  let id: string;
  try {
    id = await deps.repo.createOrder({ ...input, customer_name: input.customer_name.trim() });
  } catch (err) {
    return { ok: false, error: errorMessage(err) };
  }

  const dispatch = await dispatchOrder(deps, id, "sistema");
  return { ok: true, id, ...dispatch };
}

/**
 * Envia o pedido para a granja. Usado na criação (status "enviado") e no
 * reenvio (status "erro_envio"). Falha deixa/mantém o pedido em erro_envio.
 */
export async function dispatchOrder(
  deps: Deps,
  orderId: string,
  actorLabel: string,
): Promise<{ sent: boolean; error?: string }> {
  const order = await deps.repo.getOrder(orderId);
  if (!order) return { sent: false, error: "Pedido não encontrado" };

  const fail = async (error: string) => {
    if (order.status === "enviado") {
      await deps.repo.transitionOrder(orderId, "enviado", "erro_envio", "sistema");
    }
    return { sent: false, error };
  };

  const { granja_chat_id } = await deps.repo.getSettings();
  if (!granja_chat_id) return fail("Granja não vinculada");

  const events = await deps.repo.listEvents(orderId);
  const asSent = { ...order, status: "enviado" as const };
  try {
    const messageId = await deps.tg.sendMessage(
      granja_chat_id,
      formatOrderMessage(asSent, events),
      keyboardFor(asSent),
    );
    await deps.repo.setTelegramMessageId(orderId, messageId);
  } catch (err) {
    return fail(errorMessage(err));
  }

  if (order.status === "erro_envio") {
    await deps.repo.transitionOrder(orderId, "erro_envio", "enviado", actorLabel);
  }
  return { sent: true };
}

/** Atualiza a mensagem da granja com o status atual. Falhas só são logadas. */
async function syncTelegramMessage(deps: Deps, orderId: string): Promise<void> {
  try {
    const order = await deps.repo.getOrder(orderId);
    const { granja_chat_id } = await deps.repo.getSettings();
    if (!order?.telegram_message_id || !granja_chat_id) return;
    const events = await deps.repo.listEvents(orderId);
    await deps.tg.editMessage(
      granja_chat_id,
      order.telegram_message_id,
      formatOrderMessage(order, events),
      keyboardFor(order),
    );
  } catch (err) {
    console.error(`[pedidos] falha ao editar mensagem do pedido ${orderId}:`, errorMessage(err));
  }
}

export async function applyOrderAction(
  deps: Deps,
  params: { orderId: string; action: OrderAction; actor: Actor; actorLabel: string },
): Promise<{ ok: boolean; message: string }> {
  const order = await deps.repo.getOrder(params.orderId);
  if (!order) return { ok: false, message: "Pedido não encontrado" };

  const next = nextStatus(order.status, params.action, params.actor);
  if (!next.ok) return { ok: false, message: next.reason };

  if (params.action === "reenviar") {
    const res = await dispatchOrder(deps, order.id, params.actorLabel);
    return res.sent
      ? { ok: true, message: "Pedido reenviado para a granja" }
      : { ok: false, message: `Falha ao reenviar: ${res.error}` };
  }

  const applied = await deps.repo.transitionOrder(order.id, order.status, next.to, params.actorLabel);
  if (!applied) {
    return { ok: false, message: "Pedido foi atualizado por outra pessoa. Recarregue a página." };
  }

  await syncTelegramMessage(deps, order.id);
  return { ok: true, message: `Pedido ${STATUS_LABEL[next.to]}` };
}
