import { Badge } from "@/components/ui/badge";

type CategoryBarProps = {
  category: string;
  spent: number;
  limit: number;
  percentUsed: number;
};

function formatBRL(v: number): string {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function CategoryBar({
  category,
  spent,
  limit,
  percentUsed,
}: CategoryBarProps) {
  const barColor =
    percentUsed >= 100
      ? "bg-red-500"
      : percentUsed >= 80
        ? "bg-yellow-400"
        : "bg-green-500";

  const badgeVariant: "default" | "secondary" | "destructive" =
    percentUsed >= 100
      ? "destructive"
      : percentUsed >= 80
        ? "secondary"
        : "default";

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center gap-2">
        <span className="text-sm font-medium">{category}</span>
        <span className="text-sm text-gray-500 flex-1 text-right">
          {formatBRL(spent)} / {formatBRL(limit)}
        </span>
        <Badge variant={badgeVariant}>{percentUsed.toFixed(0)}%</Badge>
      </div>
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} rounded-full transition-all`}
          style={{ width: `${Math.min(percentUsed, 100)}%` }}
        />
      </div>
    </div>
  );
}
