# Dashboard Next.js — Implementation Plan (Plano 3/3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Pré-requisito:** Plano 1 (Backend) deve estar completo e rodando.

**Goal:** Dashboard web simples em Next.js 14 com autenticação Supabase, visualização do resumo financeiro, extrato, barras de limite por categoria e convites familiares.

**Architecture:** Next.js App Router com Server Components para dados e Client Components para interatividade. Supabase Auth para login. Chamadas à API FastAPI via `lib/api.ts` com o JWT do usuário logado.

**Tech Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, @supabase/ssr, date-fns.

## Global Constraints

- TypeScript estrito — sem `any` explícito
- Apenas BRL — valores formatados como `R$ 1.234,56`
- Next.js App Router — sem `pages/` directory
- Supabase SSR (`@supabase/ssr`) para auth em Server e Client Components
- Sem estado global (Zustand/Redux) — usar React state local + fetch
- Paleta: fundo neutro, verde para receitas/positivo, vermelho para gastos/alertas, amarelo para atenção

---

## Estrutura de Arquivos

```
frontend/
├── package.json
├── .env.local.example
├── tailwind.config.ts
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Redirect: logado → /dashboard, não → /login
│   │   ├── login/
│   │   │   └── page.tsx               # Formulário de login
│   │   ├── auth/
│   │   │   └── callback/
│   │   │       └── route.ts           # Callback do Supabase Auth
│   │   └── dashboard/
│   │       ├── layout.tsx             # Layout com nav lateral simples
│   │       ├── page.tsx               # Dashboard principal (resumo + limites)
│   │       ├── transactions/
│   │       │   └── page.tsx           # Extrato completo com filtros
│   │       ├── limits/
│   │       │   └── page.tsx           # Configurar limites por categoria
│   │       └── family/
│   │           └── page.tsx           # Convidar familiar
│   ├── components/
│   │   ├── balance-card.tsx           # Card: saldo do mês
│   │   ├── category-bar.tsx           # Barra de progresso de limite
│   │   ├── transaction-table.tsx      # Tabela de transações
│   │   ├── telegram-link.tsx          # Botão para abrir bot no Telegram
│   │   └── invite-form.tsx            # Formulário de convite
│   └── lib/
│       ├── supabase-browser.ts        # Client component Supabase client
│       ├── supabase-server.ts         # Server component Supabase client
│       └── api.ts                     # Funções de fetch para a API FastAPI
```

---

## Task 1: Setup do Projeto Next.js

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/.env.local.example`
- Create: `frontend/src/lib/supabase-browser.ts`
- Create: `frontend/src/lib/supabase-server.ts`
- Create: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces:
  - `supabase-browser.ts` → `createBrowserClient()` para Client Components
  - `supabase-server.ts` → `createServerClient()` para Server Components
  - `api.ts` → funções `getSummary`, `getTransactions`, `getLimits`, `upsertLimit`, `sendInvite`

- [ ] **Step 1: Inicializar projeto Next.js**

```bash
cd projects/my-finance-bot
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --no-eslint
```

- [ ] **Step 2: Instalar dependências**

```bash
cd frontend
npm install @supabase/supabase-js @supabase/ssr date-fns
npx shadcn@latest init
npx shadcn@latest add card table progress badge button input label
```

- [ ] **Step 3: Criar `frontend/.env.local.example`**

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=seubot
```

- [ ] **Step 4: Criar `frontend/src/lib/supabase-browser.ts`**

```typescript
import { createBrowserClient } from "@supabase/ssr";

export function createSupabaseBrowserClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

- [ ] **Step 5: Criar `frontend/src/lib/supabase-server.ts`**

```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export function createSupabaseServerClient() {
  const cookieStore = cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value;
        },
      },
    }
  );
}
```

- [ ] **Step 6: Criar `frontend/src/lib/api.ts`**

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Transaction = {
  id: string;
  amount: number;
  type: "income" | "expense";
  category: string;
  description: string;
  date: string;
  created_at: string;
};

export type CategorySummary = { category: string; total: number };

export type MonthlySummary = {
  month: string;
  total_income: number;
  total_expense: number;
  balance: number;
  by_category: CategorySummary[];
};

export type Limit = {
  id: string;
  category: string;
  monthly_limit: number;
  spent: number;
  percent_used: number;
};

async function apiFetch<T>(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json() as Promise<T>;
}

export async function getSummary(token: string, month?: string): Promise<MonthlySummary> {
  const params = month ? `?month=${month}` : "";
  return apiFetch<MonthlySummary>(`/summary/${params}`, token);
}

export async function getTransactions(
  token: string,
  filters?: { month?: string; category?: string; type?: string }
): Promise<Transaction[]> {
  const params = new URLSearchParams(
    Object.entries(filters ?? {}).filter(([, v]) => Boolean(v)) as [string, string][]
  );
  const query = params.toString() ? `?${params}` : "";
  return apiFetch<Transaction[]>(`/transactions/${query}`, token);
}

export async function getLimits(token: string): Promise<Limit[]> {
  return apiFetch<Limit[]>("/limits/", token);
}

export async function upsertLimit(
  token: string,
  category: string,
  monthly_limit: number
): Promise<Limit> {
  return apiFetch<Limit>("/limits/", token, {
    method: "POST",
    body: JSON.stringify({ category, monthly_limit }),
  });
}

export async function sendInvite(token: string, email: string): Promise<{ id: string; email: string }> {
  return apiFetch("/groups/invite", token, {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}
```

- [ ] **Step 7: Verificar que projeto compila**

```bash
cd frontend
npm run build
```

Esperado: build sem erros de TypeScript

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Next.js 14 frontend with Supabase client and API lib"
```

---

## Task 2: Autenticação (Login + Callback)

**Files:**
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/app/auth/callback/route.ts`

**Interfaces:**
- Produces: fluxo de login via Supabase (email+senha), redirecionamento para `/dashboard` após login

- [ ] **Step 1: Criar `frontend/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Assistente Financeiro",
  description: "Controle financeiro pessoal e familiar",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Criar `frontend/src/app/page.tsx`** (redireciona baseado em auth)

```tsx
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase-server";

export default async function RootPage() {
  const supabase = createSupabaseServerClient();
  const { data: { session } } = await supabase.auth.getSession();

  if (session) {
    redirect("/dashboard");
  } else {
    redirect("/login");
  }
}
```

- [ ] **Step 3: Criar `frontend/src/app/login/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const supabase = createSupabaseBrowserClient();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setError("Email ou senha incorretos.");
      setLoading(false);
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center text-xl">Assistente Financeiro</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Senha</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Entrando..." : "Entrar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Criar `frontend/src/app/auth/callback/route.ts`**

```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const cookieStore = cookies();
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          get: (name) => cookieStore.get(name)?.value,
          set: (name, value, options) => cookieStore.set({ name, value, ...options }),
          remove: (name, options) => cookieStore.delete({ name, ...options }),
        },
      }
    );
    await supabase.auth.exchangeCodeForSession(code);
  }

  return NextResponse.redirect(`${origin}/dashboard`);
}
```

- [ ] **Step 5: Testar login**

```bash
cd frontend
npm run dev
```

Abrir `http://localhost:3000` → deve redirecionar para `/login`.
Criar usuário no Supabase Dashboard → Auth → Users → Invite user.
Fazer login com as credenciais → deve redirecionar para `/dashboard`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/
git commit -m "feat: add Supabase authentication flow with login page"
```

---

## Task 3: Layout do Dashboard e Componentes Base

**Files:**
- Create: `frontend/src/app/dashboard/layout.tsx`
- Create: `frontend/src/components/balance-card.tsx`
- Create: `frontend/src/components/category-bar.tsx`
- Create: `frontend/src/components/telegram-link.tsx`

**Interfaces:**
- Produces:
  - `<BalanceCard>` — props: `totalIncome`, `totalExpense`, `balance` (numbers)
  - `<CategoryBar>` — props: `category`, `spent`, `limit`, `percentUsed`
  - `<TelegramLink>` — link para `t.me/{TELEGRAM_BOT_USERNAME}`

- [ ] **Step 1: Criar `frontend/src/app/dashboard/layout.tsx`**

```tsx
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase-server";
import Link from "next/link";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = createSupabaseServerClient();
  const { data: { session } } = await supabase.auth.getSession();

  if (!session) {
    redirect("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <span className="font-semibold text-gray-800">Assistente Financeiro</span>
        <div className="flex gap-4 text-sm">
          <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">Resumo</Link>
          <Link href="/dashboard/transactions" className="text-gray-600 hover:text-gray-900">Extrato</Link>
          <Link href="/dashboard/limits" className="text-gray-600 hover:text-gray-900">Limites</Link>
          <Link href="/dashboard/family" className="text-gray-600 hover:text-gray-900">Família</Link>
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Criar `frontend/src/components/balance-card.tsx`**

```tsx
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

export function BalanceCard({ totalIncome, totalExpense, balance, month }: BalanceCardProps) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500">Receitas</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-green-600">{formatBRL(totalIncome)}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500">Despesas</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-red-600">{formatBRL(totalExpense)}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500">Saldo — {month}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={`text-2xl font-bold ${balance >= 0 ? "text-green-700" : "text-red-700"}`}>
            {formatBRL(balance)}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Criar `frontend/src/components/category-bar.tsx`**

```tsx
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

type CategoryBarProps = {
  category: string;
  spent: number;
  limit: number;
  percentUsed: number;
};

function formatBRL(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function CategoryBar({ category, spent, limit, percentUsed }: CategoryBarProps) {
  const color =
    percentUsed >= 100 ? "bg-red-500" : percentUsed >= 80 ? "bg-yellow-400" : "bg-green-500";
  const badge =
    percentUsed >= 100 ? "destructive" : percentUsed >= 80 ? "secondary" : "default";

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium">{category}</span>
        <span className="text-sm text-gray-500">
          {formatBRL(spent)} / {formatBRL(limit)}
        </span>
        <Badge variant={badge as "default" | "secondary" | "destructive"}>
          {percentUsed.toFixed(0)}%
        </Badge>
      </div>
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all`}
          style={{ width: `${Math.min(percentUsed, 100)}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Criar `frontend/src/components/telegram-link.tsx`**

```tsx
import { Button } from "@/components/ui/button";

export function TelegramLink() {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? "";
  return (
    <a
      href={`https://t.me/${botUsername}`}
      target="_blank"
      rel="noopener noreferrer"
    >
      <Button variant="outline" size="sm">
        Abrir no Telegram
      </Button>
    </a>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add dashboard layout and base UI components"
```

---

## Task 4: Dashboard Principal

**Files:**
- Create: `frontend/src/app/dashboard/page.tsx`

**Interfaces:**
- Consumes: `getSummary`, `getLimits`, `<BalanceCard>`, `<CategoryBar>`, `<TelegramLink>`

- [ ] **Step 1: Criar `frontend/src/app/dashboard/page.tsx`**

```tsx
import { createSupabaseServerClient } from "@/lib/supabase-server";
import { getSummary, getLimits } from "@/lib/api";
import { BalanceCard } from "@/components/balance-card";
import { CategoryBar } from "@/components/category-bar";
import { TelegramLink } from "@/components/telegram-link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function DashboardPage() {
  const supabase = createSupabaseServerClient();
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";

  const today = new Date();
  const month = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;

  const [summary, limits] = await Promise.all([
    getSummary(token, month),
    getLimits(token),
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
```

- [ ] **Step 2: Testar dashboard visualmente**

```bash
npm run dev
```

Abrir `http://localhost:3000/dashboard` → verificar:
- Cards de saldo renderizam com valores do backend
- Barras de limite aparecem (se configuradas)
- Botão "Abrir no Telegram" presente

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/dashboard/page.tsx
git commit -m "feat: implement main dashboard with balance cards and category limits"
```

---

## Task 5: Página de Extrato

**Files:**
- Create: `frontend/src/components/transaction-table.tsx`
- Create: `frontend/src/app/dashboard/transactions/page.tsx`

**Interfaces:**
- Consumes: `getTransactions`, `<TransactionTable>`

- [ ] **Step 1: Criar `frontend/src/components/transaction-table.tsx`**

```tsx
import { Transaction } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

type TransactionTableProps = {
  transactions: Transaction[];
};

export function TransactionTable({ transactions }: TransactionTableProps) {
  if (transactions.length === 0) {
    return <p className="text-sm text-gray-500 text-center py-8">Nenhuma transação encontrada.</p>;
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
        {transactions.map((tx) => (
          <TableRow key={tx.id}>
            <TableCell className="text-sm text-gray-600">
              {new Date(tx.date + "T12:00:00").toLocaleDateString("pt-BR")}
            </TableCell>
            <TableCell className="text-sm">{tx.description || "—"}</TableCell>
            <TableCell>
              <Badge variant="outline">{tx.category}</Badge>
            </TableCell>
            <TableCell>
              <span className={tx.type === "income" ? "text-green-600 text-sm" : "text-red-600 text-sm"}>
                {tx.type === "income" ? "Receita" : "Despesa"}
              </span>
            </TableCell>
            <TableCell className={`text-right font-medium ${tx.type === "income" ? "text-green-600" : "text-red-600"}`}>
              {tx.type === "income" ? "+" : "-"}
              {tx.amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Criar `frontend/src/app/dashboard/transactions/page.tsx`**

```tsx
import { createSupabaseServerClient } from "@/lib/supabase-server";
import { getTransactions } from "@/lib/api";
import { TransactionTable } from "@/components/transaction-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function TransactionsPage({
  searchParams,
}: {
  searchParams: { month?: string; category?: string; type?: string };
}) {
  const supabase = createSupabaseServerClient();
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";

  const today = new Date();
  const month =
    searchParams.month ??
    `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;

  const transactions = await getTransactions(token, {
    month,
    category: searchParams.category,
    type: searchParams.type,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-gray-900">Extrato</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{month} — {transactions.length} transação(ões)</CardTitle>
        </CardHeader>
        <CardContent>
          <TransactionTable transactions={transactions} />
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Testar extrato**

Abrir `http://localhost:3000/dashboard/transactions` → verificar tabela com transações do mês atual.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/transaction-table.tsx frontend/src/app/dashboard/transactions/
git commit -m "feat: add transactions page with sortable table"
```

---

## Task 6: Páginas de Limites e Convite Familiar

**Files:**
- Create: `frontend/src/components/invite-form.tsx`
- Create: `frontend/src/app/dashboard/limits/page.tsx`
- Create: `frontend/src/app/dashboard/family/page.tsx`

**Interfaces:**
- Consumes: `getLimits`, `upsertLimit`, `sendInvite`

- [ ] **Step 1: Criar `frontend/src/app/dashboard/limits/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { getLimits, upsertLimit, Limit } from "@/lib/api";
import { CategoryBar } from "@/components/category-bar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const CATEGORIES = ["Alimentação","Transporte","Moradia","Saúde","Educação","Lazer","Vestuário","Outros"];

export default function LimitsPage() {
  const [limits, setLimits] = useState<Limit[]>([]);
  const [selected, setSelected] = useState(CATEGORIES[0]);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const supabase = createSupabaseBrowserClient();

  async function loadLimits() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const data = await getLimits(session.access_token);
    setLimits(data);
  }

  useEffect(() => { loadLimits(); }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    try {
      await upsertLimit(session.access_token, selected, parseFloat(value));
      setMessage(`Limite de R$ ${parseFloat(value).toLocaleString("pt-BR", { minimumFractionDigits: 2 })} definido para ${selected}.`);
      setValue("");
      await loadLimits();
    } catch {
      setMessage("Erro ao salvar limite. Tente novamente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Limites por Categoria</h1>

      <Card>
        <CardHeader><CardTitle className="text-base">Definir Limite</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSave} className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="text-sm text-gray-600 mb-1 block">Categoria</label>
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="w-full border rounded-md px-3 py-2 text-sm"
              >
                {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="text-sm text-gray-600 mb-1 block">Limite mensal (R$)</label>
              <Input
                type="number"
                min="1"
                step="0.01"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                required
                placeholder="500,00"
              />
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? "Salvando..." : "Salvar"}
            </Button>
          </form>
          {message && <p className="mt-2 text-sm text-green-700">{message}</p>}
        </CardContent>
      </Card>

      {limits.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Limites Configurados</CardTitle></CardHeader>
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
    </div>
  );
}
```

- [ ] **Step 2: Criar `frontend/src/components/invite-form.tsx`**

```tsx
"use client";

import { useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { sendInvite } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function InviteForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const supabase = createSupabaseBrowserClient();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    try {
      await sendInvite(session.access_token, email);
      setStatus("success");
      setMessage(`Convite enviado para ${email}.`);
      setEmail("");
    } catch {
      setStatus("error");
      setMessage("Erro ao enviar convite. Verifique o email e tente novamente.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <Label htmlFor="invite-email">Email do familiar</Label>
        <Input
          id="invite-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="familiar@example.com"
          className="mt-1"
        />
      </div>
      <Button type="submit" disabled={status === "loading"}>
        {status === "loading" ? "Enviando..." : "Enviar Convite"}
      </Button>
      {message && (
        <p className={`text-sm ${status === "success" ? "text-green-700" : "text-red-600"}`}>
          {message}
        </p>
      )}
    </form>
  );
}
```

- [ ] **Step 3: Criar `frontend/src/app/dashboard/family/page.tsx`**

```tsx
import { InviteForm } from "@/components/invite-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function FamilyPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Acesso Familiar</h1>
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle className="text-base">Convidar Familiar</CardTitle>
          <p className="text-sm text-gray-500">
            O familiar convidado terá acesso aos mesmos dados financeiros do seu grupo.
          </p>
        </CardHeader>
        <CardContent>
          <InviteForm />
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Testar todas as páginas**

```bash
npm run dev
```

Verificar:
- `/dashboard` — resumo e saldo
- `/dashboard/transactions` — extrato
- `/dashboard/limits` — formulário + barras de progresso
- `/dashboard/family` — formulário de convite

- [ ] **Step 5: Build final**

```bash
npm run build
```

Esperado: build sem erros de TypeScript ou compilação

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: add limits configuration and family invite pages"
```

---

## Verificação Final do Plano 3

Checklist completo:

- [ ] Login com usuário Supabase → redireciona para `/dashboard`
- [ ] Dashboard mostra saldo correto do mês
- [ ] Barras de limite aparecem com cores corretas (verde/amarelo/vermelho)
- [ ] Extrato lista transações do mês
- [ ] Página de limites: criar/atualizar limite → reflete na barra
- [ ] Convite familiar: enviar email → retorna confirmação
- [ ] Botão "Abrir no Telegram" presente no dashboard
- [ ] `npm run build` passa sem erros

---

*Documento sujeito à revisão do responsável pelo projeto.*
