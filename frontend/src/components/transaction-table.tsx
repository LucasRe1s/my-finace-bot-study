import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { Transaction } from "@/lib/api";

type TransactionTableProps = {
  transactions: Transaction[];
};

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-");
  return `${day}/${month}/${year}`;
}

export function TransactionTable({ transactions }: TransactionTableProps) {
  if (transactions.length === 0) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        Nenhuma transação encontrada.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Data</TableHead>
          <TableHead>Descrição</TableHead>
          <TableHead>Categoria</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead className="text-right">Valor</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {transactions.map((t) => (
          <TableRow key={t.id}>
            <TableCell className="text-gray-500">
              {formatDate(t.date)}
            </TableCell>
            <TableCell>{t.description}</TableCell>
            <TableCell>
              <Badge variant="outline">{t.category}</Badge>
            </TableCell>
            <TableCell>
              {t.type === "income" ? (
                <Badge variant="default">Receita</Badge>
              ) : (
                <Badge variant="destructive">Despesa</Badge>
              )}
            </TableCell>
            <TableCell
              className={`text-right font-medium ${
                t.type === "income" ? "text-green-600" : "text-red-600"
              }`}
            >
              {t.type === "income" ? "+" : "-"}
              {formatBRL(Math.abs(t.amount))}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
