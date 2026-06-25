import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

type BalanceCardProps = {
  totalIncome: number;
  totalExpense: number;
  balance: number;
  month: string;
};

export function BalanceCard({
  totalIncome,
  totalExpense,
  balance,
  month,
}: BalanceCardProps) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500">
            Receitas
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-green-600">
            {formatBRL(totalIncome)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500">
            Despesas
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-red-600">
            {formatBRL(totalExpense)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500">
            Saldo &mdash; {month}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p
            className={`text-2xl font-bold ${
              balance >= 0 ? "text-green-700" : "text-red-700"
            }`}
          >
            {formatBRL(balance)}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
