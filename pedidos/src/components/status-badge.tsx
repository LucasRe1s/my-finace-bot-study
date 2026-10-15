import { STATUS_LABEL } from "@/lib/status";
import type { OrderStatus } from "@/lib/types";

const COLORS: Record<OrderStatus, string> = {
  erro_envio: "bg-red-100 text-red-800",
  enviado: "bg-amber-100 text-amber-800",
  aceito: "bg-sky-100 text-sky-800",
  recusado: "bg-red-100 text-red-800",
  em_entrega: "bg-indigo-100 text-indigo-800",
  entregue: "bg-emerald-100 text-emerald-800",
  cancelado: "bg-slate-200 text-slate-700",
};

export function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${COLORS[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}
