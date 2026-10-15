import type { Order, OrderEvent, OrderStatus, Product, Settings } from "./types";

export type NewOrderInput = {
  customer_name: string;
  notes: string;
  created_by: string;
  items: { product_id: string; boxes: number }[];
};

export type ProductInput = {
  id?: string;
  name: string;
  description: string;
  units_per_box: number;
};

/** Acesso a dados do módulo. Implementação real em repo-supabase.ts. */
export interface Repo {
  getSettings(): Promise<Settings>;
  saveSettings(patch: Partial<Settings>): Promise<void>;
  listProducts(opts?: { includeInactive?: boolean }): Promise<Product[]>;
  saveProduct(p: ProductInput): Promise<void>;
  setProductActive(id: string, active: boolean): Promise<void>;
  /** Cria pedido (status "enviado") e itens atomicamente; lança erro se produto inválido. */
  createOrder(input: NewOrderInput): Promise<string>;
  getOrder(id: string): Promise<Order | null>;
  listOrders(status?: OrderStatus): Promise<Order[]>;
  listEvents(orderId: string): Promise<OrderEvent[]>;
  /** Muda o status só se o atual for `from`, registrando o evento. False se já mudou. */
  transitionOrder(id: string, from: OrderStatus, to: OrderStatus, actor: string): Promise<boolean>;
  setTelegramMessageId(id: string, messageId: number): Promise<void>;
}
