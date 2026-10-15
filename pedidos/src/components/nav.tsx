import Link from "next/link";
import { signOut } from "@/app/login/actions";

const LINKS = [
  { href: "/pedidos", label: "Pedidos" },
  { href: "/pedidos/novo", label: "Novo pedido" },
  { href: "/produtos", label: "Produtos" },
  { href: "/configuracoes", label: "Configurações" },
];

export function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <nav className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-sm">
          <span className="mr-2 font-semibold">Pedidos</span>
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="text-slate-600 hover:text-slate-900">
              {l.label}
            </Link>
          ))}
          <form action={signOut} className="ml-auto">
            <button className="text-slate-500 hover:text-slate-900">Sair</button>
          </form>
        </nav>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-6">
        <h1 className="mb-4 text-xl font-semibold">{title}</h1>
        {children}
      </main>
    </>
  );
}

export function Notice({ text, tone = "info" }: { text?: string; tone?: "info" | "error" }) {
  if (!text) return null;
  const style =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-800"
      : "border-emerald-200 bg-emerald-50 text-emerald-800";
  return <p className={`mb-4 rounded-md border px-3 py-2 text-sm ${style}`}>{text}</p>;
}
