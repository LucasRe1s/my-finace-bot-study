"use client";

import { useEffect, useState } from "react";
import { getLimits, upsertLimit } from "@/lib/api";
import type { Limit } from "@/lib/api";
import { CategoryBar } from "@/components/category-bar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const DEFAULT_CATEGORIES = [
  "Alimentação",
  "Transporte",
  "Moradia",
  "Saúde",
  "Educação",
  "Lazer",
  "Vestuário",
  "Outros",
];

export default function LimitsPage() {
  const [token, setToken] = useState<string>("");
  const [limits, setLimits] = useState<Limit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [limitValue, setLimitValue] = useState<string>("");
  const [submitStatus, setSubmitStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      const { createBrowserClient } = await import("@supabase/ssr");
      const supabase = createBrowserClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
      );
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const accessToken = session?.access_token ?? "";
      setToken(accessToken);

      try {
        const data = await getLimits(accessToken);
        setLimits(data);
      } catch {
        setError("Erro ao carregar limites.");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedCategory || !limitValue) return;

    const value = parseFloat(limitValue.replace(",", "."));
    if (isNaN(value) || value <= 0) {
      setSubmitError("Informe um valor valido maior que zero.");
      return;
    }

    setSubmitStatus("loading");
    setSubmitError(null);

    try {
      await upsertLimit(token, selectedCategory, value);
      const updated = await getLimits(token);
      setLimits(updated);
      setSubmitStatus("success");
      setSelectedCategory("");
      setLimitValue("");
    } catch (err) {
      setSubmitStatus("error");
      setSubmitError(
        err instanceof Error ? err.message : "Erro ao salvar limite."
      );
    }
  }

  const categories =
    limits.length > 0
      ? Array.from(new Set([...limits.map((l) => l.category), ...DEFAULT_CATEGORIES]))
      : DEFAULT_CATEGORIES;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">
          Limites por Categoria
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Definir ou Atualizar Limite</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="category-select">Categoria</Label>
              <select
                id="category-select"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                required
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="" disabled>
                  Selecione uma categoria
                </option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="limit-value">Limite mensal (R$)</Label>
              <Input
                id="limit-value"
                type="text"
                inputMode="decimal"
                placeholder="Ex: 500,00"
                value={limitValue}
                onChange={(e) => setLimitValue(e.target.value)}
                disabled={submitStatus === "loading"}
                required
              />
            </div>

            {submitStatus === "success" && (
              <p className="text-sm text-green-600">Limite salvo com sucesso.</p>
            )}
            {submitStatus === "error" && submitError && (
              <p className="text-sm text-red-600">{submitError}</p>
            )}

            <Button
              type="submit"
              disabled={submitStatus === "loading" || !selectedCategory}
              className="w-full"
            >
              {submitStatus === "loading" ? "Salvando..." : "Salvar Limite"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {loading && (
        <p className="text-sm text-gray-500">Carregando limites...</p>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && limits.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Limites Cadastrados</CardTitle>
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

      {!loading && !error && limits.length === 0 && (
        <p className="text-sm text-gray-500">
          Nenhum limite cadastrado. Defina um limite acima para comecar a
          acompanhar seus gastos por categoria.
        </p>
      )}
    </div>
  );
}
