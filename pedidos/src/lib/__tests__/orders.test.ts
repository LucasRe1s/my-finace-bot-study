import { beforeEach, describe, expect, it } from "vitest";
import { applyOrderAction, createOrder } from "@/lib/orders";
import { FakeRepo, FakeTelegram } from "./fakes";

let repo: FakeRepo;
let tg: FakeTelegram;
const input = {
  customer_name: "Mercado X",
  notes: "",
  created_by: "user-1",
  items: [{ product_id: "p1", boxes: 10 }],
};

beforeEach(() => {
  repo = new FakeRepo();
  tg = new FakeTelegram();
});

describe("createOrder", () => {
  it("grava, envia para a granja com botões e guarda o message_id", async () => {
    const res = await createOrder({ repo, tg }, input);

    expect(res).toEqual({ ok: true, id: expect.any(String), sent: true });
    expect(tg.sent).toHaveLength(1);
    expect(tg.sent[0].chatId).toBe(999);
    expect(tg.sent[0].text).toContain("- 10 cx Ovo branco grande (30 un/cx)");
    expect(tg.sent[0].keyboard?.[0].map((b) => b.text)).toEqual(["✅ Aceitar", "❌ Recusar"]);
    const order = await repo.getOrder(res.ok ? res.id : "");
    expect(order?.status).toBe("enviado");
    expect(order?.telegram_message_id).toBe(1001);
  });

  it("sem granja vinculada: pedido fica em erro_envio", async () => {
    repo.settings.granja_chat_id = null;
    const res = await createOrder({ repo, tg }, input);

    expect(res).toMatchObject({ ok: true, sent: false, error: "Granja não vinculada" });
    expect(repo.orders[0].status).toBe("erro_envio");
    expect(repo.events.at(-1)).toMatchObject({ from_status: "enviado", to_status: "erro_envio", actor: "sistema" });
  });

  it("falha do Telegram: pedido fica em erro_envio com o motivo", async () => {
    tg.failSend = true;
    const res = await createOrder({ repo, tg }, input);

    expect(res).toMatchObject({ ok: true, sent: false });
    expect(res.ok && res.error).toContain("chat not found");
    expect(repo.orders[0].status).toBe("erro_envio");
  });

  it.each([
    [{ ...input, customer_name: "  " }, "Informe o nome do mercado"],
    [{ ...input, items: [] }, "Adicione pelo menos um item"],
    [{ ...input, items: [{ product_id: "p1", boxes: 0 }] }, "Quantidade de caixas inválida"],
    [{ ...input, items: [{ product_id: "p1", boxes: 1.5 }] }, "Quantidade de caixas inválida"],
  ])("valida entrada sem gravar (%#)", async (bad, error) => {
    expect(await createOrder({ repo, tg }, bad)).toEqual({ ok: false, error });
    expect(repo.orders).toHaveLength(0);
    expect(tg.sent).toHaveLength(0);
  });

  it("produto inativo: erro sem enviar", async () => {
    const res = await createOrder({ repo, tg }, { ...input, items: [{ product_id: "p2", boxes: 1 }] });
    expect(res.ok).toBe(false);
    expect(tg.sent).toHaveLength(0);
  });
});

describe("applyOrderAction", () => {
  async function newOrder() {
    const res = await createOrder({ repo, tg }, input);
    if (!res.ok) throw new Error("setup");
    return res.id;
  }

  it("cancelar pela web muda status e edita a mensagem removendo botões", async () => {
    const id = await newOrder();
    const res = await applyOrderAction({ repo, tg }, { orderId: id, action: "cancelar", actor: "web", actorLabel: "web:ana@x.com" });

    expect(res).toEqual({ ok: true, message: "Pedido cancelado" });
    expect(repo.orders[0].status).toBe("cancelado");
    expect(tg.edited[0]).toMatchObject({ chatId: 999, messageId: 1001, keyboard: null });
    expect(tg.edited[0].text).toContain("❌ Cancelado pelo escritório");
  });

  it("transição inválida não altera nem edita", async () => {
    const id = await newOrder();
    const res = await applyOrderAction({ repo, tg }, { orderId: id, action: "entregar", actor: "web", actorLabel: "web:a" });

    expect(res.ok).toBe(false);
    expect(repo.orders[0].status).toBe("enviado");
    expect(tg.edited).toHaveLength(0);
  });

  it("corrida perdida: avisa que outra pessoa atualizou", async () => {
    const id = await newOrder();
    repo.loseNextRace = true;
    const res = await applyOrderAction({ repo, tg }, { orderId: id, action: "cancelar", actor: "web", actorLabel: "web:a" });

    expect(res).toEqual({ ok: false, message: "Pedido foi atualizado por outra pessoa. Recarregue a página." });
  });

  it("falha ao editar a mensagem não desfaz a mudança de status", async () => {
    const id = await newOrder();
    tg.failEdit = true;
    const res = await applyOrderAction({ repo, tg }, { orderId: id, action: "cancelar", actor: "web", actorLabel: "web:a" });

    expect(res.ok).toBe(true);
    expect(repo.orders[0].status).toBe("cancelado");
  });

  it("pedido inexistente", async () => {
    const res = await applyOrderAction({ repo, tg }, { orderId: "x", action: "cancelar", actor: "web", actorLabel: "web:a" });
    expect(res).toEqual({ ok: false, message: "Pedido não encontrado" });
  });

  it("reenviar: envia de novo e volta para enviado", async () => {
    tg.failSend = true;
    const id = await newOrder();
    tg.failSend = false;

    const res = await applyOrderAction({ repo, tg }, { orderId: id, action: "reenviar", actor: "web", actorLabel: "web:a" });

    expect(res).toEqual({ ok: true, message: "Pedido reenviado para a granja" });
    expect(repo.orders[0].status).toBe("enviado");
    expect(repo.orders[0].telegram_message_id).toBe(1001);
    expect(tg.sent[0].keyboard).not.toBeNull();
  });

  it("reenviar com nova falha continua em erro_envio", async () => {
    tg.failSend = true;
    const id = await newOrder();
    const res = await applyOrderAction({ repo, tg }, { orderId: id, action: "reenviar", actor: "web", actorLabel: "web:a" });

    expect(res.ok).toBe(false);
    expect(res.message).toContain("chat not found");
    expect(repo.orders[0].status).toBe("erro_envio");
  });
});
