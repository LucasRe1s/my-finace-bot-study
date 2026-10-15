import type { NewOrderInput, ProductInput, Repo } from "@/lib/repo";
import type { TelegramClient } from "@/lib/telegram";
import type { InlineKeyboard, Order, OrderEvent, OrderStatus, Product, Settings } from "@/lib/types";

export class FakeRepo implements Repo {
  settings: Settings = { granja_chat_id: 999, link_code: null, link_code_expires_at: null };
  products: Product[] = [
    { id: "p1", name: "Ovo branco grande", description: "", units_per_box: 30, active: true },
    { id: "p2", name: "Ovo caipira", description: "", units_per_box: 20, active: false },
  ];
  orders: Order[] = [];
  events: (OrderEvent & { order_id: string })[] = [];
  /** Força transitionOrder a perder a corrida. */
  loseNextRace = false;
  private seq = 0;
  private clock = Date.parse("2026-10-14T17:00:00Z");

  private tick() {
    this.clock += 60_000;
    return new Date(this.clock).toISOString();
  }

  async getSettings() {
    return { ...this.settings };
  }
  async saveSettings(patch: Partial<Settings>) {
    Object.assign(this.settings, patch);
  }
  async listProducts(opts?: { includeInactive?: boolean }) {
    return this.products.filter((p) => opts?.includeInactive || p.active);
  }
  async saveProduct(p: ProductInput) {
    const existing = this.products.find((x) => x.id === p.id);
    if (existing) Object.assign(existing, p);
    else this.products.push({ ...p, id: `p${this.products.length + 1}`, active: true });
  }
  async setProductActive(id: string, active: boolean) {
    this.products.find((p) => p.id === id)!.active = active;
  }
  async createOrder(input: NewOrderInput) {
    const items = input.items.map((i) => {
      const p = this.products.find((x) => x.id === i.product_id && x.active);
      if (!p) throw new Error(`Produto inexistente ou inativo: ${i.product_id}`);
      return { product_id: p.id, product_name: p.name, units_per_box: p.units_per_box, boxes: i.boxes };
    });
    const id = `00000000-0000-4000-8000-${String(++this.seq).padStart(12, "0")}`;
    const created_at = this.tick();
    this.orders.push({
      id,
      number: this.seq,
      customer_name: input.customer_name,
      notes: input.notes,
      status: "enviado",
      telegram_message_id: null,
      created_at,
      items,
    });
    this.events.push({ order_id: id, from_status: null, to_status: "enviado", actor: "web", created_at });
    return id;
  }
  async getOrder(id: string) {
    const o = this.orders.find((x) => x.id === id);
    return o ? structuredClone(o) : null;
  }
  async listOrders(status?: OrderStatus) {
    return this.orders.filter((o) => !status || o.status === status);
  }
  async listEvents(orderId: string) {
    return this.events.filter((e) => e.order_id === orderId);
  }
  async transitionOrder(id: string, from: OrderStatus, to: OrderStatus, actor: string) {
    const o = this.orders.find((x) => x.id === id)!;
    if (this.loseNextRace) {
      this.loseNextRace = false;
      return false;
    }
    if (o.status !== from) return false;
    o.status = to;
    this.events.push({ order_id: id, from_status: from, to_status: to, actor, created_at: this.tick() });
    return true;
  }
  async setTelegramMessageId(id: string, messageId: number) {
    this.orders.find((x) => x.id === id)!.telegram_message_id = messageId;
  }
}

type Sent = { chatId: number; text: string; keyboard: InlineKeyboard | null };

export class FakeTelegram implements TelegramClient {
  sent: Sent[] = [];
  edited: (Sent & { messageId: number })[] = [];
  answers: { id: string; text?: string }[] = [];
  failSend = false;
  failEdit = false;

  async sendMessage(chatId: number, text: string, keyboard: InlineKeyboard | null) {
    if (this.failSend) throw new Error("Telegram sendMessage: Bad Request: chat not found");
    this.sent.push({ chatId, text, keyboard });
    return 1000 + this.sent.length;
  }
  async editMessage(chatId: number, messageId: number, text: string, keyboard: InlineKeyboard | null) {
    if (this.failEdit) throw new Error("Telegram editMessageText: message to edit not found");
    this.edited.push({ chatId, messageId, text, keyboard });
  }
  async answerCallback(id: string, text?: string) {
    this.answers.push({ id, text });
  }
}
