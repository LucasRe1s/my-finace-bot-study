# O que falta — my-finance-bot

> Atualizado em 16/07/2026. Backend, bot e dashboard funcionando, incluindo criacao de grupo, convite por link e vinculo de conta Telegram.

---

## Concluido

| Plano | Tarefas | Status |
|---|---|---|
| P1 — Backend FastAPI | T1 a T8 + GET /groups/members | Completo |
| P2 — Bot Telegram + Agente | T1 a T5 + auth por usuario | Completo |
| P3 — Dashboard Next.js | T1 a T6 | Completo |
| Agente Groq | Troca Claude Haiku por Groq llama-3.3-70b | Completo |
| Auth bot sem formulario | JWT por usuario, bot_users via tabela users | Completo |
| Migrations Supabase | 001 a 010 (schema, bot auth, grants, vinculo Telegram) | Completo |
| AUTH-01 | 401 no dashboard web — validacao via JWKS (ES256) | Completo |
| Criar grupo | Endpoint, tool do bot e tela web | Completo |
| Convite sem email | Link copiavel + pagina /convite/[token] (signup + accept) | Completo |
| Vinculo Telegram | Codigo de uso unico, migra dados de identidade so-bot pre-existente | Completo |
| Blindagem do agente | Detecta vazamento de tool-call e erro bruto do provedor (Groq) | Completo |

---

## Pendente — Em andamento

### SEC-01: policies de RLS permissivas para `anon` (ver SECURITY.md)

O bot precisa operar sem sessao de usuario Supabase, e isso levou a policies
`USING (true)` para o role `anon` em varias tabelas (users, conversations,
group_members, transactions, invites, groups, telegram_link_codes). Como a
anon key e publica (fica no bundle do frontend), qualquer pessoa com ela
consegue ler/escrever esses dados direto na API do Supabase, sem passar pelo
backend. Detalhe completo e recomendacao de correcao (service_role key para
operacoes do bot) em [`SECURITY.md`](SECURITY.md).

---

## Pendente — Proximo ciclo

### DEPLOY-01: Deploy Render + Vercel

**Backend (Render):**
- Dockerfile ou buildpack Python
- Variaveis de ambiente: todas do `backend/.env`
- Porta: `$PORT` (Render injeta)
- Comando: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Frontend (Vercel):**
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL` apontando para o Render
- `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=finncyBot`

**Bot Telegram (Render — servico separado ou mesmo servico):**
- Comando de start: `python -m tgbot.runner`
- Variaveis: todas do `.env` incluindo `GROQ_API_KEY`

### OPENAI-01: `OPENAI_API_KEY` no .env esta vazio

Campo existe em `config.py` mas nao e usado. Remover ou documentar que e legado.

---

## Debitos tecnicos

| Origem | Descricao |
|---|---|
| P1-T4 | `InviteCreate.email` usa `str` em vez de `EmailStr` |
| P1-T5 | `?month=` sem validacao de formato — ValueError vira 500 |
| P3-T2 | `getSession()` no servidor — trocar por `getUser()` |
| P3-T2 | Auth callback sem redirect quando `code` ausente |
| P3-T6 | `family/page.tsx` exibe user_id truncado — melhorar com tabela profiles |
| BOT-01 | Ver SEC-01 acima — escopo cresceu para varias tabelas, nao so `users` |
| ~~DEBUG-01~~ | ~~Remover `/debug/token` endpoint antes do deploy~~ — feito |
| SEC-02 (era P1-T2) | `invites_accept_update` usa `USING(true)` — qualquer autenticado aceita qualquer convite |
| SEC-03 | Senha minima de 6 caracteres no signup via convite |
| CORS-01 | `allow_origins=["*"]` no backend — restringir a origem do frontend em producao |
