import { notFound } from "next/navigation";
import { Notice, Shell } from "@/components/nav";
import { StatusBadge } from "@/components/status-badge";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";
import { formatDateTime } from "@/lib/format";
import { STATUS_LABEL, availableActions } from "@/lib/status";
import type { OrderAction } from "@/lib/types";
import { orderAction } from "../actions";

const ACTION_BUTTON: Partial<Record<OrderAction, { label: string; className: string }>> = {
  entregar: { label: "Marcar como entregue", className: "btn-primary" },
  reenviar: { label: "Reenviar para a granja", className: "btn-primary" },
  cancelar: { label: "Cancelar pedido", className: "btn-danger" },
};

function actorName(actor: string) {
  if (actor === "granja") return "granja";
  if (actor === "sistema") return "sistema";
  return actor.replace(/^web:?/, "") || "escritório";
}

export default async function PedidoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ msg?: string; erro?: string }>;
}) {
  await requireUser();
  const { id } = await params;
  const { msg, erro } = await searchParams;
  const { repo } = getDeps();
  const order = await repo.getOrder(id);
  if (!order) notFound();
  const events = await repo.listEvents(id);
  const actions = availableActions(order.status, "web");

  return (
    <Shell title={`Pedido #${order.number}`}>
      <Notice text={msg} />
      <Notice text={erro} tone="error" />

      <div className="card space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-lg font-medium">{order.customer_name}</p>
            <p className="text-sm text-slate-500">Criado em {formatDateTime(order.created_at)}</p>
          </div>
          <StatusBadge status={order.status} />
        </div>

        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1 font-normal">Produto</th>
              <th className="py-1 text-right font-normal">Caixas</th>
              <th className="py-1 text-right font-normal">Unidades</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((i, idx) => (
              <tr key={idx} className="border-t border-slate-100">
                <td className="py-1.5">{i.product_name}</td>
                <td className="py-1.5 text-right">{i.boxes}</td>
                <td className="py-1.5 text-right">{i.boxes * i.units_per_box}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {order.notes && <p className="text-sm"><span className="text-slate-500">Obs.:</span> {order.notes}</p>}

        {actions.length > 0 && (
          <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
            {actions.map((a) => (
              <form key={a} action={orderAction}>
                <input type="hidden" name="order_id" value={order.id} />
                <input type="hidden" name="action" value={a} />
                <button className={ACTION_BUTTON[a]!.className}>{ACTION_BUTTON[a]!.label}</button>
              </form>
            ))}
          </div>
        )}
      </div>

      <h2 className="mb-2 mt-6 text-sm font-medium text-slate-500">Histórico</h2>
      <ol className="space-y-1 text-sm">
        {events.map((e, idx) => (
          <li key={idx}>
            <span className="text-slate-500">{formatDateTime(e.created_at)}</span>{" "}
            {e.from_status ? `${STATUS_LABEL[e.from_status]} → ` : ""}
            <strong>{STATUS_LABEL[e.to_status]}</strong>{" "}
            <span className="text-slate-500">({actorName(e.actor)})</span>
          </li>
        ))}
      </ol>
    </Shell>
  );
}
