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

## Stack

| Camada | Tecnologia |
|---|---|
| Bot | python-telegram-bot v21 |
| Agente IA | Agno + Groq (llama-3.3-70b) |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Banco | Supabase (PostgreSQL) |
| Auth | Supabase Auth (JWT) |
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
