import type { Actor, OrderAction, OrderStatus } from "./types";

export const STATUS_LABEL: Record<OrderStatus, string> = {
  erro_envio: "erro no envio",
  enviado: "enviado",
  aceito: "aceito",
  recusado: "recusado",
  em_entrega: "em entrega",
  entregue: "entregue",
  cancelado: "cancelado",
};

type Transition = { from: OrderStatus[]; to: OrderStatus; actor: Actor };

const TRANSITIONS: Record<OrderAction, Transition> = {
  reenviar: { from: ["erro_envio"], to: "enviado", actor: "web" },
  aceitar: { from: ["enviado"], to: "aceito", actor: "granja" },
  recusar: { from: ["enviado"], to: "recusado", actor: "granja" },
  sair_entrega: { from: ["aceito"], to: "em_entrega", actor: "granja" },
  entregar: { from: ["em_entrega"], to: "entregue", actor: "web" },
  cancelar: { from: ["enviado", "aceito", "em_entrega", "erro_envio"], to: "cancelado", actor: "web" },
};

const FINAL: OrderStatus[] = ["recusado", "entregue", "cancelado"];

export function isFinal(status: OrderStatus): boolean {
  return FINAL.includes(status);
}

export function nextStatus(
  current: OrderStatus,
  action: OrderAction,
  actor: Actor,
): { ok: true; to: OrderStatus } | { ok: false; reason: string } {
  const t = TRANSITIONS[action];
  if (t.actor !== actor) {
    return { ok: false, reason: "Ação não permitida" };
  }
  if (t.from.includes(current)) {
    return { ok: true, to: t.to };
  }
  if (isFinal(current) || current === t.to) {
    return { ok: false, reason: `Pedido já ${STATUS_LABEL[current]}` };
  }
  return { ok: false, reason: `Ação indisponível: pedido está ${STATUS_LABEL[current]}` };
}

/** Ações que o ator pode disparar a partir do status atual. */
export function availableActions(current: OrderStatus, actor: Actor): OrderAction[] {
  return (Object.keys(TRANSITIONS) as OrderAction[]).filter(
    (a) => TRANSITIONS[a].actor === actor && TRANSITIONS[a].from.includes(current),
  );
}
