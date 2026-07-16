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

export type GroupMember = {
  user_id: string;
  role: "owner" | "member";
};

export function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

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

export async function getSummary(
  token: string,
  month?: string
): Promise<MonthlySummary> {
  const params = month ? `?month=${month}` : "";
  return apiFetch<MonthlySummary>(`/summary/${params}`, token);
}

export async function getTransactions(
  token: string,
  filters?: { month?: string; category?: string; type?: string }
): Promise<Transaction[]> {
  const params = new URLSearchParams(
    Object.entries(filters ?? {}).filter(([, v]) => Boolean(v)) as [
      string,
      string,
    ][]
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

export async function getGroupMembers(token: string): Promise<GroupMember[]> {
  return apiFetch<GroupMember[]>("/groups/members", token);
}

export async function createGroup(
  token: string,
  name: string
): Promise<{ id: string; name: string; owner_id: string }> {
  return apiFetch("/groups/", token, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export type TelegramLinkCode = {
  code: string;
  expires_at: string;
};

export async function createTelegramLinkCode(
  token: string
): Promise<TelegramLinkCode> {
  return apiFetch<TelegramLinkCode>("/auth/telegram-link-code", token, {
    method: "POST",
  });
}

export async function sendInvite(
  token: string,
  email: string
): Promise<{ id: string; email: string; token: string }> {
  return apiFetch("/groups/invite", token, {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export type InvitePreview = {
  email: string;
  group_name: string;
};

export async function getInvitePreview(
  inviteToken: string
): Promise<InvitePreview> {
  const res = await fetch(`${API_URL}/groups/invite/${inviteToken}`);
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json() as Promise<InvitePreview>;
}

export async function acceptInvite(
  accessToken: string,
  inviteToken: string
): Promise<{ message: string }> {
  return apiFetch(
    `/groups/accept?token=${encodeURIComponent(inviteToken)}`,
    accessToken,
    { method: "POST" }
  );
}
