# Fase 6: Débitos técnicos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar os débitos que sobraram antes do uso real: entrada inválida que vira 500, autenticação do painel baseada em sessão não verificada, callback de login sem tratamento de erro, senha fraca e geração de código sem limite.

**Architecture:** Correções pequenas e independentes. No backend, validação declarativa do `month` e reuso do `SlidingWindowLimiter` do núcleo. No frontend, decisões de acesso passam a usar `getClaims()`, que verifica a assinatura do JWT (o projeto usa chaves assimétricas), em vez de `getSession()`, que só lê o cookie.

**Tech Stack:** FastAPI, pytest, Next.js, @supabase/ssr + supabase-js 2.108.

**Spec:** `specs/2026-10-07-producao-e-familia-design.md` (seção "Fase 6").

## Global Constraints

- Backend: `.venv/bin/pytest -q` em `backend/`. Frontend: `npx tsc --noEmit` e `next build` em `frontend/` (o frontend não tem suíte de testes).
- Comentários e mensagens em português; sem travessão (—) em texto novo.
- Commits com `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Fora desta fase

- **Remover `users.telegram_id`:** só depois que todo usuário antigo tiver identidade em `user_identities` (o fallback adota na primeira mensagem). A consulta para conferir fica no PENDENTE.
- **Confirmação do vínculo na web (SECURITY item 2):** o código já é de uso único, vale 10 minutos e só é consumido dentro do bot. O risco restante (alguém ver o código na tela) não justifica um segundo passo agora. Fica registrado no SECURITY.

---

### Task 1: `month` validado (P1-T5)

**Files:**
- Create: `backend/app/routers/params.py`
- Modify: `backend/app/routers/transactions.py`, `backend/app/routers/summary.py`
- Test: `backend/tests/test_month_param.py`

- [ ] **Step 1: Teste que falha**

```python
import pytest


@pytest.mark.parametrize("path", ["/transactions/", "/summary/"])
@pytest.mark.parametrize("month", ["2026-13", "2026-6", "junho", "2026-06-01", "26-06"])
def test_invalid_month_is_422(client, valid_token, path, month):
    response = client.get(path, params={"month": month}, headers={"Authorization": f"Bearer {valid_token}"})
    assert response.status_code == 422
```

(A validação roda antes do handler, então não há acesso ao banco nesses casos.)

- [ ] **Step 2: Rodar e ver falhar** (hoje `2026-13` estoura `calendar.monthrange` com 500 e `junho` estoura o `split`).

- [ ] **Step 3: Implementação**

`backend/app/routers/params.py`:

```python
from typing import Annotated, Optional

from fastapi import Query

# YYYY-MM com mes de 01 a 12; qualquer outra coisa vira 422 antes do handler.
Month = Annotated[
    Optional[str],
    Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Formato YYYY-MM, ex: 2026-06"),
]
```

Em `transactions.list_transactions` e `summary.get_summary`, o parâmetro vira `month: Month = None` (import `from .params import Month`).

- [ ] **Step 4: Rodar a suíte.**
- [ ] **Step 5: Commit** `fix(api): month invalido responde 422 em vez de 500 (P1-T5)`

---

### Task 2: Limite na geração de código de vínculo

**Files:**
- Modify: `backend/app/routers/auth_link.py`
- Test: `backend/tests/test_auth_link.py`

- [ ] **Step 1: Teste que falha**

```python
def test_link_code_generation_is_rate_limited(client, valid_token, monkeypatch):
    from app.routers import auth_link
    from core.rate_limit import SlidingWindowLimiter

    monkeypatch.setattr(auth_link, "_code_limiter", SlidingWindowLimiter(max_events=2, window_seconds=600))
    mock_db = MagicMock()
    with patch("app.routers.auth_link.get_supabase", return_value=mock_db):
        codes = [client.post("/auth/telegram-link-code", headers={"Authorization": f"Bearer {valid_token}"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação** em `auth_link.py`:

```python
from core.rate_limit import SlidingWindowLimiter

# Cada codigo vale 10 min; 5 por janela sobra para quem errou e evita spam na tabela.
_code_limiter = SlidingWindowLimiter(max_events=5, window_seconds=600)
```

e, no início de `create_telegram_link_code`:

```python
    if not _code_limiter.allow(user["id"]):
        raise HTTPException(status_code=429, detail="Muitos códigos gerados. Aguarde alguns minutos.")
```

(volta o import de `HTTPException`).

- [ ] **Step 4: Rodar a suíte.**
- [ ] **Step 5: Commit** `fix(auth): limite de 5 codigos de vinculo a cada 10 minutos`

---

### Task 3: Painel com JWT verificado (P3-T2)

**Files:**
- Modify: `frontend/src/lib/supabase-server.ts`, `frontend/src/proxy.ts`, `frontend/src/app/dashboard/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/dashboard/family/page.tsx`, `frontend/src/app/dashboard/transactions/page.tsx`

- [ ] **Step 1: Helper** em `supabase-server.ts`:

```ts
/**
 * Token do usuario para chamar a API, so depois de verificar a assinatura do
 * JWT com getClaims(). getSession() sozinho le o cookie sem verificar e nao
 * deve decidir acesso. (A API tambem valida o token.)
 */
export async function getVerifiedAccessToken(): Promise<string | null> {
  const supabase = await createSupabaseServerClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) return null;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}
```

- [ ] **Step 2: Decisões de acesso com `getClaims()`**
  - `proxy.ts`: `const { data } = await supabase.auth.getClaims(); const isAuthenticated = Boolean(data?.claims);` e as duas condições usam `isAuthenticated` no lugar de `session`.
  - `dashboard/layout.tsx` e `app/page.tsx`: mesmo padrão para o `redirect`.
- [ ] **Step 3: Páginas que precisam do token** (`dashboard/page.tsx`, `family/page.tsx`, `transactions/page.tsx`): `const token = (await getVerifiedAccessToken()) ?? "";` no lugar do `getSession()`.
- [ ] **Step 4:** `npx tsc --noEmit` e `next build`; `grep -rn "getSession" src` só pode sobrar no helper e na página de limites (componente de cliente, no navegador).
- [ ] **Step 5: Commit** `fix(frontend): acesso ao painel decidido com JWT verificado (getClaims)`

---

### Task 4: Callback de login e senha mínima (P3-T2, SEC-03)

**Files:**
- Modify: `frontend/src/app/auth/callback/route.ts`, `frontend/src/app/login/page.tsx`, `frontend/src/app/convite/[token]/page.tsx`

- [ ] **Step 1: Callback**: sem `code` ou com erro no `exchangeCodeForSession`, redirecionar para `/login?erro=link` em vez de `/dashboard`:

```ts
  if (!code) {
    return NextResponse.redirect(`${origin}/login?erro=link`);
  }
  ...
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    return NextResponse.redirect(`${origin}/login?erro=link`);
  }
  return NextResponse.redirect(`${origin}/dashboard`);
```

- [ ] **Step 2: Login** mostra "Link de acesso inválido ou expirado. Entre com email e senha." quando `?erro=link` (via `useSearchParams`, dentro de `<Suspense>` se o build exigir).
- [ ] **Step 3: Senha:** `minLength={10}` no cadastro do convite, com dica "Mínimo de 10 caracteres." abaixo do campo no modo cadastro. No painel do Supabase (Authentication > Providers > Email), configurar o mínimo de 10 e, se o plano permitir, a proteção contra senhas vazadas. Isso fica no README, porque o frontend sozinho não impede cadastro direto pela API do Supabase.
- [ ] **Step 4:** `npx tsc --noEmit` e `next build`.
- [ ] **Step 5: Commit** `fix(frontend): callback de login trata erro e senha minima de 10 (SEC-03)`

---

### Task 5: Documentação

- [ ] PENDENTE: tabela de débitos zerada (exceto a remoção do `users.telegram_id`, com a consulta de conferência); Fase 6 em "Concluido".
- [ ] SECURITY: senha, `getClaims` e limite de código para "Já corrigido"; item do vínculo com a justificativa.
- [ ] README: configuração de senha no painel do Supabase.
- [ ] Spec: Fase 6 aponta para este plano.
- [ ] Commit `docs: fase 6 (debitos tecnicos)`.
