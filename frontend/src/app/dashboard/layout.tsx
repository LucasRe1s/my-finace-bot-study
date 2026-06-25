import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase-server";
import Link from "next/link";
import { LogoutButton } from "@/components/logout-button";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createSupabaseServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    redirect("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <span className="font-semibold text-gray-800">
          Assistente Financeiro
        </span>
        <div className="flex gap-4 text-sm items-center">
          <Link
            href="/dashboard"
            className="text-gray-600 hover:text-gray-900"
          >
            Resumo
          </Link>
          <Link
            href="/dashboard/transactions"
            className="text-gray-600 hover:text-gray-900"
          >
            Extrato
          </Link>
          <Link
            href="/dashboard/limits"
            className="text-gray-600 hover:text-gray-900"
          >
            Limites
          </Link>
          <Link
            href="/dashboard/family"
            className="text-gray-600 hover:text-gray-900"
          >
            Família
          </Link>
          <LogoutButton />
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
