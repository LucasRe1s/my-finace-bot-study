import { createSupabaseServerClient } from "@/lib/supabase-server";
import { getTransactions } from "@/lib/api";
import { TransactionTable } from "@/components/transaction-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Props = {
  searchParams: Promise<{ month?: string; category?: string; type?: string }>;
};

export default async function TransactionsPage({ searchParams }: Props) {
  const params = await searchParams;

  const supabase = await createSupabaseServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";

  const today = new Date();
  const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  const month = params.month ?? currentMonth;

  const transactions = await getTransactions(token, {
    month,
    category: params.category,
    type: params.type,
  }).catch(() => []);

  const [year, monthNum] = month.split("-");
  const monthLabel = new Date(Number(year), Number(monthNum) - 1, 1).toLocaleDateString(
    "pt-BR",
    { month: "long", year: "numeric" }
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Extrato de Transações</h1>
      </div>

      <div className="flex flex-wrap gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className="font-medium text-gray-700">Mês:</span>
          <span className="capitalize">{monthLabel}</span>
        </div>
        {params.category && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span className="font-medium text-gray-700">Categoria:</span>
            <span>{params.category}</span>
          </div>
        )}
        {params.type && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span className="font-medium text-gray-700">Tipo:</span>
            <span>{params.type === "income" ? "Receita" : "Despesa"}</span>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {transactions.length} {transactions.length === 1 ? "transação" : "transações"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TransactionTable transactions={transactions} />
        </CardContent>
      </Card>
    </div>
  );
}
