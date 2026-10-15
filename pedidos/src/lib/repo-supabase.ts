import type { SupabaseClient } from "@supabase/supabase-js";
import type { NewOrderInput, ProductInput, Repo } from "./repo";
import type { Order, OrderEvent, OrderStatus, Product, Settings } from "./types";

const ORDER_COLUMNS =
  "id, number, customer_name, notes, status, telegram_message_id, created_at, " +
  "items:order_items(product_id, product_name, units_per_box, boxes)";

// Postgres: invalid_text_representation (ex.: id que não é uuid)
const INVALID_UUID = "22P02";

function check<T>(res: { data: T | null; error: { message: string } | null }): T {
  if (res.error) throw new Error(res.error.message);
  return res.data as T;
}

export class SupabaseRepo implements Repo {
  constructor(private db: SupabaseClient) {}

  async getSettings(): Promise<Settings> {
    return check(
      await this.db
        .from("settings")
        .select("granja_chat_id, link_code, link_code_expires_at")
        .eq("id", true)
        .single(),
    );
  }

  async saveSettings(patch: Partial<Settings>) {
    check(await this.db.from("settings").update(patch).eq("id", true));
  }

  async listProducts(opts?: { includeInactive?: boolean }): Promise<Product[]> {
    let query = this.db
      .from("products")
      .select("id, name, description, units_per_box, active")
      .order("active", { ascending: false })
      .order("name");
    if (!opts?.includeInactive) query = query.eq("active", true);
    return check(await query);
  }

  async saveProduct({ id, ...fields }: ProductInput) {
    if (id) check(await this.db.from("products").update(fields).eq("id", id));
    else check(await this.db.from("products").insert(fields));
  }

  async setProductActive(id: string, active: boolean) {
    check(await this.db.from("products").update({ active }).eq("id", id));
  }

  async createOrder(input: NewOrderInput): Promise<string> {
    return check(
      await this.db.rpc("create_order", {
        p_customer_name: input.customer_name,
        p_notes: input.notes,
        p_created_by: input.created_by,
        p_items: input.items,
      }),
    );
  }

  async getOrder(id: string): Promise<Order | null> {
    const res = await this.db.from("orders").select(ORDER_COLUMNS).eq("id", id).maybeSingle();
    if (res.error?.code === INVALID_UUID) return null;
    return check(res) as unknown as Order | null;
  }

  async listOrders(status?: OrderStatus): Promise<Order[]> {
    let query = this.db
      .from("orders")
      .select(ORDER_COLUMNS)
      .order("created_at", { ascending: false })
      .limit(200);
    if (status) query = query.eq("status", status);
    return check(await query) as unknown as Order[];
  }

  async listEvents(orderId: string): Promise<OrderEvent[]> {
    return check(
      await this.db
        .from("order_events")
        .select("from_status, to_status, actor, created_at")
        .eq("order_id", orderId)
        .order("created_at"),
    );
  }

  async transitionOrder(id: string, from: OrderStatus, to: OrderStatus, actor: string) {
    return check(
      await this.db.rpc("transition_order", {
        p_order_id: id,
        p_from: from,
        p_to: to,
        p_actor: actor,
      }),
    ) as boolean;
  }

  async setTelegramMessageId(id: string, messageId: number) {
    check(await this.db.from("orders").update({ telegram_message_id: messageId }).eq("id", id));
  }
}
