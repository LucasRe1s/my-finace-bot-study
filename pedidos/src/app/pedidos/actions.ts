"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";
import { applyOrderAction, createOrder } from "@/lib/orders";
import type { OrderAction } from "@/lib/types";

const WEB_ACTIONS = new Set<OrderAction>(["entregar", "cancelar", "reenviar"]);

export async function createOrderAction(_prev: string | null, formData: FormData): Promise<string | null> {
  const user = await requireUser();

  let items: { product_id: string; boxes: number }[];
  try {
    items = JSON.parse(String(formData.get("items") ?? "[]"));
  } catch {
    return "Itens inválidos";
  }

  const res = await createOrder(getDeps(), {
    customer_name: String(formData.get("customer_name") ?? ""),
    notes: String(formData.get("notes") ?? ""),
    created_by: user.id,
    items: items.map((i) => ({ product_id: String(i.product_id), boxes: Number(i.boxes) })),
  });
  if (!res.ok) return res.error;

  revalidatePath("/pedidos");
  const query = res.sent
    ? "msg=" + encodeURIComponent("Pedido enviado para a granja")
    : "erro=" + encodeURIComponent(`Pedido salvo, mas não foi enviado: ${res.error}`);
  redirect(`/pedidos/${res.id}?${query}`);
}

export async function orderAction(formData: FormData) {
  const user = await requireUser();
  const orderId = String(formData.get("order_id") ?? "");
  const action = String(formData.get("action") ?? "") as OrderAction;
  if (!WEB_ACTIONS.has(action)) throw new Error("Ação inválida");

  const res = await applyOrderAction(getDeps(), {
    orderId,
    action,
    actor: "web",
    actorLabel: `web:${user.email}`,
  });

  revalidatePath("/pedidos");
  redirect(`/pedidos/${orderId}?${res.ok ? "msg" : "erro"}=${encodeURIComponent(res.message)}`);
}
