import { describe, expect, it } from "vitest";
import { formatOrderMessage, keyboardFor, parseCallbackData } from "@/lib/format";
import type { Order, OrderEvent } from "@/lib/types";

const ID = "8f6c2a1e-1111-4222-8333-944455556666";

function order(overrides: Partial<Order> = {}): Order {
  return {
    id: ID,
    number: 42,
    customer_name: "Mercado X",
    notes: "",
    status: "enviado",
    telegram_message_id: null,
    created_at: "2026-10-14T17:00:00Z",
    items: [
      { product_id: "p1", product_name: "Ovo branco grande", units_per_box: 30, boxes: 10 },
      { product_id: "p2", product_name: "Ovo vermelho médio", units_per_box: 30, boxes: 5 },
    ],
    ...overrides,
  };
}

describe("formatOrderMessage", () => {
  it("lista cliente e itens", () => {
    const text = formatOrderMessage(order(), []);
    expect(text).toContain("Novo pedido #42");
    expect(text).toContain("Cliente: Mercado X");
    expect(text).toContain("- 10 cx Ovo branco grande (30 un/cx)");
    expect(text).toContain("- 5 cx Ovo vermelho médio (30 un/cx)");
    expect(text).not.toContain("Obs.");
  });

  it("inclui observação quando existe", () => {
    expect(formatOrderMessage(order({ notes: "entregar até sexta" }), [])).toContain(
      "Obs.: entregar até sexta",
    );
  });

  it("acrescenta uma linha por mudança de status, no horário de Brasília", () => {
    const events: OrderEvent[] = [
      { from_status: null, to_status: "enviado", actor: "web", created_at: "2026-10-14T17:00:00Z" },
      { from_status: "enviado", to_status: "aceito", actor: "granja", created_at: "2026-10-14T17:32:00Z" },
      { from_status: "aceito", to_status: "cancelado", actor: "web:ana@x.com", created_at: "2026-10-14T18:05:00Z" },
    ];
    const text = formatOrderMessage(order({ status: "cancelado" }), events);
    expect(text).toContain("✅ Aceito em 14/10 14:32");
    expect(text).toContain("❌ Cancelado pelo escritório em 14/10 15:05");
    expect(text).not.toContain("ana@x.com");
  });
});

describe("keyboardFor", () => {
  it("enviado: aceitar e recusar", () => {
    expect(keyboardFor(order())).toEqual([
      [
        { text: "✅ Aceitar", callback_data: `aceitar:${ID}` },
        { text: "❌ Recusar", callback_data: `recusar:${ID}` },
      ],
    ]);
  });

  it("aceito: saiu para entrega", () => {
    expect(keyboardFor(order({ status: "aceito" }))).toEqual([
      [{ text: "🚚 Saiu para entrega", callback_data: `sair_entrega:${ID}` }],
    ]);
  });

  it("demais status: sem botões", () => {
    for (const status of ["em_entrega", "entregue", "recusado", "cancelado", "erro_envio"] as const) {
      expect(keyboardFor(order({ status }))).toBeNull();
    }
  });

  it("callback_data cabe no limite de 64 bytes do Telegram", () => {
    const data = keyboardFor(order({ status: "aceito" }))![0][0].callback_data;
    expect(new TextEncoder().encode(data).length).toBeLessThanOrEqual(64);
  });
});

describe("parseCallbackData", () => {
  it("lê ação e pedido", () => {
    expect(parseCallbackData(`aceitar:${ID}`)).toEqual({ action: "aceitar", orderId: ID });
  });

  it("rejeita ação desconhecida, ação da web e lixo", () => {
    expect(parseCallbackData(`apagar:${ID}`)).toBeNull();
    expect(parseCallbackData(`cancelar:${ID}`)).toBeNull();
    expect(parseCallbackData("aceitar:nao-e-uuid")).toBeNull();
    expect(parseCallbackData("")).toBeNull();
  });
});
