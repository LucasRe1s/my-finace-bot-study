import { Notice, Shell } from "@/components/nav";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";
import type { Product } from "@/lib/types";
import { saveProductAction, toggleProductAction } from "./actions";

export default async function ProdutosPage({
  searchParams,
}: {
  searchParams: Promise<{ msg?: string; erro?: string }>;
}) {
  await requireUser();
  const { msg, erro } = await searchParams;
  const products = await getDeps().repo.listProducts({ includeInactive: true });

  return (
    <Shell title="Produtos">
      <Notice text={msg} />
      <Notice text={erro} tone="error" />

      <section className="card mb-6">
        <h2 className="mb-3 text-sm font-medium">Novo produto</h2>
        <ProductFields />
      </section>

      <ul className="space-y-3">
        {products.map((p) => (
          <li key={p.id} className={`card ${p.active ? "" : "opacity-60"}`}>
            <details>
              <summary className="flex cursor-pointer list-none items-center gap-3">
                <span className="flex-1">
                  <span className="font-medium">{p.name}</span>{" "}
                  <span className="text-sm text-slate-500">{p.units_per_box} un/cx</span>
                  {!p.active && <span className="ml-2 text-xs text-slate-500">(inativo)</span>}
                  {p.description && <span className="block text-sm text-slate-500">{p.description}</span>}
                </span>
                <span className="text-sm text-slate-500">Editar</span>
              </summary>
              <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
                <ProductFields product={p} />
                <form action={toggleProductAction}>
                  <input type="hidden" name="id" value={p.id} />
                  <input type="hidden" name="active" value={String(!p.active)} />
                  <button className={p.active ? "btn-danger" : "btn-secondary"}>
                    {p.active ? "Desativar" : "Reativar"}
                  </button>
                </form>
              </div>
            </details>
          </li>
        ))}
      </ul>
    </Shell>
  );
}

function ProductFields({ product }: { product?: Product }) {
  return (
    <form action={saveProductAction} className="grid gap-3 sm:grid-cols-[2fr_1fr]">
      {product && <input type="hidden" name="id" value={product.id} />}
      <input className="input" name="name" placeholder="Nome (ex.: Ovo branco grande)" defaultValue={product?.name} required />
      <input
        className="input"
        name="units_per_box"
        type="number"
        min={1}
        step={1}
        placeholder="Unidades por caixa"
        defaultValue={product?.units_per_box}
        required
      />
      <input
        className="input sm:col-span-2"
        name="description"
        placeholder="Descrição (opcional)"
        defaultValue={product?.description}
      />
      <div className="sm:col-span-2">
        <button className="btn-primary">{product ? "Salvar alterações" : "Cadastrar"}</button>
      </div>
    </form>
  );
}
