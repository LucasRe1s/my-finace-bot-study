# my-finance-bot

Bot de auxílio financeiro pessoal/familiar via Telegram, com entrada de dados em linguagem natural, histórico de movimentações e dashboard web. Moeda única: BRL.

## Arquitetura

```
[Telegram] ←→ [python-telegram-bot v21]
                        ↓
              [Agno Agent + Tools]
                        ↓
              [FastAPI Backend (Python 3.12)]
                        ↓
              [Supabase (PostgreSQL + Auth)]
                        ↑
              [Next.js Dashboard] ←→ [FastAPI Backend]
```

Detalhes completos em [`specs/2026-06-25-design.md`](specs/2026-06-25-design.md).

## Funcionalidades

**Pelo Telegram:**
- Registrar receitas/despesas em linguagem natural, com confirmação antes de gravar
- Consultar extrato, resumo mensal e limites por categoria
- Definir limite mensal por categoria, com alerta ao atingir 80%/100%
- Criar o grupo financeiro (`criar_grupo`) quando ainda não tiver um
- Vincular a conta do Telegram a uma conta web já existente via `/start <código>`

**Pelo dashboard web:**
- Resumo financeiro, extrato e limites por categoria
- Criar grupo financeiro (se ainda não tiver um)
- Convidar familiares por link (não há envio de email — o link é gerado e copiado manualmente)
- Gerar código para vincular o Telegram à conta web

## Stack

| Camada | Tecnologia |
|---|---|
| Bot | python-telegram-bot v21 |
| Agente IA | Agno + Groq (llama-3.3-70b-versatile) |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Banco | Supabase (PostgreSQL) |
| Auth | Supabase Auth (JWT via JWKS, chaves ES256) + JWT próprio do bot (HS256) |
| Frontend | Next.js, Tailwind, shadcn/ui |
| Deploy | Render (backend + bot) + Vercel (frontend) |

## Estrutura do repositório

```
backend/
  app/          # FastAPI: rotas, auth, config, database
  agent/        # Agente Agno (bot.py, tools.py, prompts.py, history.py)
  tgbot/        # Handlers e runner do bot Telegram
  supabase/     # Migrations SQL
  tests/        # Testes pytest
frontend/       # Dashboard Next.js
specs/          # Design e planos de implementação
```

## Pré-requisitos

- Python 3.12+
- Node.js 20+
- Conta Supabase (projeto com Postgres + Auth)
- Bot Telegram criado via [@BotFather](https://t.me/BotFather)
- Chave de API Groq

## Configuração

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

Crie um `.env` a partir de `.env.example` e preencha:

```
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_JWT_SECRET=
TELEGRAM_BOT_TOKEN=
GROQ_API_KEY=
```

Rode as migrations em `backend/supabase/migrations/` (em ordem numérica) no SQL editor do Supabase.

### Frontend

```bash
cd frontend
npm install
```

Configure `.env.local` com:

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=
```

## Rodando localmente

```bash
# Backend (API)
cd backend
uvicorn app.main:app --reload

# Bot Telegram
cd backend
python -m tgbot.runner

# Frontend
cd frontend
npm run dev
```

## Testes

```bash
cd backend
pytest
```

## Status do projeto

Ver [`PENDENTE.md`](PENDENTE.md) para pendências em andamento e débitos técnicos conhecidos.

## Segurança

Ver [`SECURITY.md`](SECURITY.md) para o levantamento de vulnerabilidades conhecidas — em especial, o item crítico sobre as policies de RLS permissivas para o role `anon` (necessárias hoje para o bot funcionar sem sessão de usuário, mas que expõem dados de todos os usuários para quem tiver a anon key).
