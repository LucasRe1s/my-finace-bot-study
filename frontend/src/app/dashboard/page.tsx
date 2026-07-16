import { createSupabaseServerClient } from "@/lib/supabase-server";
import { getSummary, getLimits } from "@/lib/api";
import { BalanceCard } from "@/components/balance-card";
import { CategoryBar } from "@/components/category-bar";
import { TelegramLink } from "@/components/telegram-link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function DashboardPage() {
  const supabase = await createSupabaseServerClient();
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";

  const today = new Date();
  const month = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;

  const [summary, limits] = await Promise.all([
    getSummary(token, month).catch(() => ({
      month,
      total_income: 0,
      total_expense: 0,
      balance: 0,
      by_category: [],
    })),
    getLimits(token).catch(() => []),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Resumo Financeiro</h1>
        <TelegramLink />
      </div>

      <BalanceCard
        totalIncome={summary.total_income}
        totalExpense={summary.total_expense}
        balance={summary.balance}
        month={summary.month}
      />

      {limits.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Limites por Categoria</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {limits.map((lim) => (
              <CategoryBar
                key={lim.category}
                category={lim.category}
                spent={lim.spent}
                limit={lim.monthly_limit}
                percentUsed={lim.percent_used}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {summary.by_category.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Gastos por Categoria</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {summary.by_category.map((item) => (
                <div key={item.category} className="flex justify-between py-2 text-sm">
                  <span>{item.category}</span>
                  <span className="font-medium text-red-600">
                    {item.total.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
