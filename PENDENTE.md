# O que falta — my-finance-bot

> Atualizado em 26/06/2026. Backend e bot funcionando. Frontend com 401 em investigação.

---

## Concluido

| Plano | Tarefas | Status |
|---|---|---|
| P1 — Backend FastAPI | T1 a T8 + GET /groups/members | Completo |
| P2 — Bot Telegram + Agente | T1 a T5 + auth por usuario | Completo |
| P3 — Dashboard Next.js | T1 a T6 | Completo |
| Agente Groq | Troca Claude Haiku por Groq llama-3.3-70b | Completo |
| Auth bot sem formulario | JWT por usuario, bot_users via tabela users | Completo |
| Migrations Supabase | 001 schema, 002 bot auth, 003 grants anon | Completo |

---

## Pendente — Em andamento

### AUTH-01: 401 no dashboard web (token Supabase x backend)

**Problema:** O token emitido pelo Supabase Auth nao passa na validacao do backend (`jwt.decode` com HS256 + secret base64-decoded).

**Hipoteses em investigacao:**
- Supabase pode estar usando RS256 (assimetrico) em projetos novos
- `aud` claim pode ser diferente de `"authenticated"`
- Secret pode precisar de tratamento diferente

**Proximos passos:**
1. Inspecionar token real via `/debug/token` endpoint
2. Verificar `alg` e `aud` do token
3. Ajustar `auth.py` conforme necessario
4. Remover endpoint `/debug/token` apos correcao

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
| P1-T2 | `invites_accept_update` usa `USING(true)` — qualquer autenticado aceita qualquer convite |
| P1-T4 | `InviteCreate.email` usa `str` em vez de `EmailStr` |
| P1-T5 | `?month=` sem validacao de formato — ValueError vira 500 |
| P3-T2 | `getSession()` no servidor — trocar por `getUser()` |
| P3-T2 | Auth callback sem redirect quando `code` ausente |
| P3-T6 | `family/page.tsx` exibe user_id truncado — melhorar com tabela profiles |
| BOT-01 | `users_bot_read` policy expoe todos os usuarios para role anon — usar service_role em producao |
| DEBUG-01 | Remover `/debug/token` endpoint antes do deploy |
