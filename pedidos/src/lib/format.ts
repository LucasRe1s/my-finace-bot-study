import { availableActions } from "./status";
import type { InlineKeyboard, Order, OrderAction, OrderEvent, OrderStatus } from "./types";

const DATE_FORMAT = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** "14/10 14:32" no horário de Brasília. */
export function formatDateTime(iso: string): string {
  const parts = Object.fromEntries(
    DATE_FORMAT.formatToParts(new Date(iso)).map((p) => [p.type, p.value]),
  );
  return `${parts.day}/${parts.month} ${parts.hour}:${parts.minute}`;
}

const EVENT_LINE: Partial<Record<OrderStatus, string>> = {
  aceito: "✅ Aceito",
  recusado: "❌ Recusado",
  em_entrega: "🚚 Saiu para entrega",
  entregue: "📦 Entregue",
  cancelado: "❌ Cancelado pelo escritório",
};

export function formatOrderMessage(order: Order, events: OrderEvent[]): string {
  const lines = [
    `Novo pedido #${order.number}`,
    `Cliente: ${order.customer_name}`,
    ...order.items.map(
      (i) => `- ${i.boxes} cx ${i.product_name} (${i.units_per_box} un/cx)`,
    ),
  ];
  if (order.notes.trim()) {
    lines.push(`Obs.: ${order.notes.trim()}`);
  }

  const history = events
    .filter((e) => e.from_status !== null && EVENT_LINE[e.to_status])
    .map((e) => `${EVENT_LINE[e.to_status]} em ${formatDateTime(e.created_at)}`);
  if (history.length) {
    lines.push("", ...history);
  }
  return lines.join("\n");
}

const BUTTON_TEXT: Partial<Record<OrderAction, string>> = {
  aceitar: "✅ Aceitar",
  recusar: "❌ Recusar",
  sair_entrega: "🚚 Saiu para entrega",
};

export function keyboardFor(order: Pick<Order, "id" | "status">): InlineKeyboard | null {
  const actions = availableActions(order.status, "granja");
  if (!actions.length) return null;
  return [
    actions.map((a) => ({ text: BUTTON_TEXT[a]!, callback_data: `${a}:${order.id}` })),
  ];
}

const GRANJA_ACTIONS = new Set<OrderAction>(["aceitar", "recusar", "sair_entrega"]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseCallbackData(
  data: string,
): { action: OrderAction; orderId: string } | null {
  const [action, orderId, ...rest] = data.split(":");
  if (rest.length || !GRANJA_ACTIONS.has(action as OrderAction) || !UUID.test(orderId ?? "")) {
    return null;
  }
  return { action: action as OrderAction, orderId };
}
