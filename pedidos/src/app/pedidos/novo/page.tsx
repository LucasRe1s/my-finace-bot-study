import Link from "next/link";
import { Shell } from "@/components/nav";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";
import { OrderForm } from "./order-form";

export default async function NovoPedidoPage() {
  await requireUser();
  const products = await getDeps().repo.listProducts();

  return (
    <Shell title="Novo pedido">
      {products.length === 0 ? (
        <p className="text-sm text-slate-500">
          Cadastre pelo menos um produto antes. <Link href="/produtos" className="underline">Ir para Produtos</Link>
        </p>
      ) : (
        <OrderForm products={products} />
      )}
    </Shell>
  );
}
