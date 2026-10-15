"use client";

import { useActionState, useState } from "react";
import type { Product } from "@/lib/types";
import { createOrderAction } from "../actions";

type Row = { key: number; product_id: string; boxes: string };

export function OrderForm({ products }: { products: Product[] }) {
  const [error, action, pending] = useActionState(createOrderAction, null);
  const [rows, setRows] = useState<Row[]>([{ key: 0, product_id: products[0].id, boxes: "" }]);

  const update = (key: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const addRow = () =>
    setRows((rs) => [...rs, { key: Math.max(...rs.map((r) => r.key)) + 1, product_id: products[0].id, boxes: "" }]);
  const removeRow = (key: number) => setRows((rs) => rs.filter((r) => r.key !== key));

  const items = rows.map((r) => ({ product_id: r.product_id, boxes: Number(r.boxes) }));
  const totalBoxes = items.reduce((sum, i) => sum + (Number.isFinite(i.boxes) ? i.boxes : 0), 0);

  return (
    <form action={action} className="card space-y-5">
      <label className="block space-y-1 text-sm">
        <span className="font-medium">Mercado</span>
        <input className="input" name="customer_name" placeholder="Ex.: Mercado X" required autoFocus />
      </label>

      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-medium">Itens</legend>
        {rows.map((row) => (
          <div key={row.key} className="flex gap-2">
            <select
              className="input flex-1"
              value={row.product_id}
              onChange={(e) => update(row.key, { product_id: e.target.value })}
              aria-label="Produto"
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.units_per_box} un/cx)
                </option>
              ))}
            </select>
            <input
              className="input w-24"
              type="number"
              min={1}
              step={1}
              inputMode="numeric"
              placeholder="cx"
              value={row.boxes}
              onChange={(e) => update(row.key, { boxes: e.target.value })}
              aria-label="Caixas"
              required
            />
            <button
              type="button"
              className="btn-secondary"
              onClick={() => removeRow(row.key)}
              disabled={rows.length === 1}
              aria-label="Remover item"
            >
              ✕
            </button>
          </div>
        ))}
        <button type="button" className="btn-secondary" onClick={addRow}>
          + Adicionar item
        </button>
      </fieldset>

      <label className="block space-y-1 text-sm">
        <span className="font-medium">Observação (opcional)</span>
        <textarea className="input" name="notes" rows={2} placeholder="Ex.: entregar até sexta" />
      </label>

      <input type="hidden" name="items" value={JSON.stringify(items)} />
      {error && <p className="text-sm text-red-700">{error}</p>}

      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">Total: {totalBoxes} cx</span>
        <button className="btn-primary" disabled={pending}>
          {pending ? "Enviando..." : "Enviar para a granja"}
        </button>
      </div>
    </form>
  );
}
