import { beforeEach, describe, expect, it } from "vitest";
import { createOrder } from "@/lib/orders";
import { generateLinkCode, handleTelegramUpdate } from "@/lib/webhook";
import { FakeRepo, FakeTelegram } from "./fakes";

let repo: FakeRepo;
let tg: FakeTelegram;
const now = () => new Date("2026-10-14T12:00:00Z");
const deps = () => ({ repo, tg, now });

beforeEach(() => {
  repo = new FakeRepo();
  tg = new FakeTelegram();
});

function startMessage(text: string, chatId = 555) {
  return { update_id: 1, message: { message_id: 1, chat: { id: chatId }, text } };
}

function callback(data: string, chatId = 999) {
  return {
    update_id: 2,
    callback_query: { id: "cb1", data, message: { message_id: 1001, chat: { id: chatId } } },
  };
}

describe("/start com código", () => {
  beforeEach(() => {
    repo.settings = { granja_chat_id: null, link_code: "ABCD2345", link_code_expires_at: "2026-10-15T00:00:00Z" };
  });

  it("código válido vincula o chat e invalida o código", async () => {
    await handleTelegramUpdate(deps(), startMessage("/start abcd2345"));

    expect(repo.settings).toEqual({ granja_chat_id: 555, link_code: null, link_code_expires_at: null });
    expect(tg.sent[0]).toMatchObject({ chatId: 555 });
    expect(tg.sent[0].text).toContain("vinculado");
  });

  it("código expirado não vincula", async () => {
    repo.settings.link_code_expires_at = "2026-10-14T11:59:00Z";
    await handleTelegramUpdate(deps(), startMessage("/start ABCD2345"));

    expect(repo.settings.granja_chat_id).toBeNull();
    expect(tg.sent[0].text).toContain("inválido ou expirado");
  });

  it("código errado não vincula", async () => {
    await handleTelegramUpdate(deps(), startMessage("/start ZZZZ9999"));
    expect(repo.settings.granja_chat_id).toBeNull();
    expect(tg.sent[0].text).toContain("inválido ou expirado");
  });

  it("/start sem código explica como vincular", async () => {
    await handleTelegramUpdate(deps(), startMessage("/start"));
    expect(repo.settings.granja_chat_id).toBeNull();
    expect(tg.sent[0].text).toContain("Configurações");
  });

  it("sem código gerado, nenhum código é aceito", async () => {
    repo.settings.link_code = null;
    await handleTelegramUpdate(deps(), startMessage("/start ABCD2345"));
    expect(repo.settings.granja_chat_id).toBeNull();
  });
});

describe("botões da granja", () => {
  let orderId: string;

  beforeEach(async () => {
    const res = await createOrder({ repo, tg }, {
      customer_name: "Mercado X",
      notes: "",
      created_by: "u1",
      items: [{ product_id: "p1", boxes: 10 }],
    });
    if (!res.ok) throw new Error("setup");
    orderId = res.id;
  });

  it("aceitar muda status, edita a mensagem e responde o clique", async () => {
    await handleTelegramUpdate(deps(), callback(`aceitar:${orderId}`));

    expect(repo.orders[0].status).toBe("aceito");
    expect(repo.events.at(-1)?.actor).toBe("granja");
    expect(tg.edited[0].keyboard?.[0][0].text).toBe("🚚 Saiu para entrega");
    expect(tg.answers).toEqual([{ id: "cb1", text: "Pedido aceito" }]);
  });

  it("clique duplicado não muda nada", async () => {
    await handleTelegramUpdate(deps(), callback(`aceitar:${orderId}`));
    await handleTelegramUpdate(deps(), callback(`aceitar:${orderId}`));

    expect(repo.events.filter((e) => e.to_status === "aceito")).toHaveLength(1);
    expect(tg.answers.at(-1)).toEqual({ id: "cb1", text: "Pedido já aceito" });
  });

  it("chat que não é a granja é recusado", async () => {
    await handleTelegramUpdate(deps(), callback(`aceitar:${orderId}`, 123));

    expect(repo.orders[0].status).toBe("enviado");
    expect(tg.answers).toEqual([{ id: "cb1", text: "Não autorizado" }]);
  });

  it("callback inválido (ex.: cancelar, que é da web) é recusado", async () => {
    await handleTelegramUpdate(deps(), callback(`cancelar:${orderId}`));

    expect(repo.orders[0].status).toBe("enviado");
    expect(tg.answers).toEqual([{ id: "cb1", text: "Ação inválida" }]);
  });
});

it("ignora updates desconhecidos", async () => {
  await handleTelegramUpdate(deps(), { update_id: 3, edited_message: {} });
  await handleTelegramUpdate(deps(), { update_id: 4, message: { chat: { id: 1 }, text: "oi" } });
  await handleTelegramUpdate(deps(), null);
  expect(tg.sent).toHaveLength(0);
});

it("generateLinkCode gera 8 caracteres sem ambíguos", () => {
  const codes = new Set(Array.from({ length: 50 }, generateLinkCode));
  expect(codes.size).toBe(50);
  for (const c of codes) expect(c).toMatch(/^[A-HJ-NP-Z2-9]{8}$/);
});
