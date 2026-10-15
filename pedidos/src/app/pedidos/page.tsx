import Link from "next/link";
import { Shell } from "@/components/nav";
import { StatusBadge } from "@/components/status-badge";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";
import { formatDateTime } from "@/lib/format";
import { STATUS_LABEL } from "@/lib/status";
import type { OrderStatus } from "@/lib/types";

export default async function PedidosPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  await requireUser();
  const { status } = await searchParams;
  const filter = status && status in STATUS_LABEL ? (status as OrderStatus) : undefined;
  const orders = await getDeps().repo.listOrders(filter);

  return (
    <Shell title="Pedidos">
      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        <FilterLink label="Todos" active={!filter} href="/pedidos" />
        {(Object.keys(STATUS_LABEL) as OrderStatus[]).map((s) => (
          <FilterLink key={s} label={STATUS_LABEL[s]} active={filter === s} href={`/pedidos?status=${s}`} />
        ))}
      </div>

      {orders.length === 0 ? (
        <p className="text-sm text-slate-500">
          Nenhum pedido. <Link href="/pedidos/novo" className="underline">Criar pedido</Link>
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {orders.map((o) => (
            <li key={o.id}>
              <Link href={`/pedidos/${o.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50">
                <span className="w-12 text-sm text-slate-500">#{o.number}</span>
                <span className="flex-1 truncate font-medium">{o.customer_name}</span>
                <span className="hidden text-sm text-slate-500 sm:inline">
                  {o.items.reduce((sum, i) => sum + i.boxes, 0)} cx
                </span>
                <span className="hidden text-sm text-slate-500 sm:inline">{formatDateTime(o.created_at)}</span>
                <StatusBadge status={o.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Shell>
  );
}

function FilterLink({ label, href, active }: { label: string; href: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`rounded-full border px-3 py-1 ${active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white"}`}
    >
      {label}
    </Link>
  );
}
