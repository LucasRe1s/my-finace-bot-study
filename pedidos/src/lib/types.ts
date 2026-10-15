export type OrderStatus =
  | "erro_envio"
  | "enviado"
  | "aceito"
  | "recusado"
  | "em_entrega"
  | "entregue"
  | "cancelado";

export type Actor = "web" | "granja";

export type OrderAction =
  | "aceitar"
  | "recusar"
  | "sair_entrega"
  | "entregar"
  | "cancelar"
  | "reenviar";

export type Product = {
  id: string;
  name: string;
  description: string;
  units_per_box: number;
  active: boolean;
};

export type OrderItem = {
  product_id: string;
  product_name: string;
  units_per_box: number;
  boxes: number;
};

export type Order = {
  id: string;
  number: number;
  customer_name: string;
  notes: string;
  status: OrderStatus;
  telegram_message_id: number | null;
  created_at: string;
  items: OrderItem[];
};

export type OrderEvent = {
  from_status: OrderStatus | null;
  to_status: OrderStatus;
  actor: string;
  created_at: string;
};

export type Settings = {
  granja_chat_id: number | null;
  link_code: string | null;
  link_code_expires_at: string | null;
};

export type InlineKeyboard = { text: string; callback_data: string }[][];
