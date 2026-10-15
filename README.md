# my-finance-bot

Bot de auxílio financeiro pessoal/familiar via Telegram, com entrada de dados em linguagem natural, histórico de movimentações e dashboard web. Moeda única: BRL.

## Arquitetura

```
[Telegram] --webhook--> POST /telegram/webhook
                              |
        +---------------------v----------------------+
        | FastAPI (um processo)                      |
        |   python-telegram-bot v22 (sem polling)    |
        |   Agente Agno + Groq -> tools              |
        |   tools chamam a propria API em processo   |
        |   (httpx.ASGITransport, JWT do usuario)    |
        +---------------------+----------------------+
                              |
                    [Supabase (Postgres + Auth)]
                              ^
                [Next.js Dashboard] --HTTP--> FastAPI
```

O bot sobe no lifespan da API quando `TELEGRAM_MODE=webhook`. A lógica de conversa fica em
`backend/core/` e não conhece o Telegram: recebe uma `IncomingMessage` e devolve `OutgoingMessage`s.
`backend/tgbot/` (Telegram) e `backend/wabot/` (WhatsApp) são só adaptadores de canal. Cada pessoa é
identificada por canal na tabela `user_identities`. Operações sem usuário logado
(bot, preview e aceite de convite) usam a `service_role` key no backend; o role `anon` não tem
acesso às tabelas (migration 011).

Design original em [`specs/2026-06-25-design.md`](specs/2026-06-25-design.md). Roteiro atual
(produção, família, WhatsApp) em [`specs/2026-10-07-producao-e-familia-design.md`](specs/2026-10-07-producao-e-familia-design.md).

## Funcionalidades

**Pelo Telegram:**
- Registrar receitas/despesas em linguagem natural (texto ou áudio, transcrito via Whisper no Groq), com confirmação antes de gravar
- Consultar extrato, resumo mensal e limites por categoria
- Definir limite mensal por categoria, com alerta ao atingir 80%/100%
- Criar o grupo financeiro (`criar_grupo`) quando ainda não tiver um
- Vincular a conta do Telegram a uma conta web já existente via `/start <código>`
- `/convidar`: gera um link `t.me/<bot>?start=join_<token>` (uso único, 7 dias); quem abre entra no grupo sem cadastro web
- Desfazer o último lançamento próprio feito nos últimos 10 minutos
- Funciona também dentro de um grupo do Telegram (ver abaixo)
- Extrato mostra quem lançou cada transação

**Pelo dashboard web:**
- Resumo financeiro, extrato e limites por categoria
- Criar grupo financeiro (se ainda não tiver um)
- Convidar familiares por link (não há envio de email: o link é gerado e copiado manualmente)
- Membros do grupo e autor de cada transação aparecem pelo nome
- Gerar código para vincular o Telegram à conta web

## Stack

| Camada | Tecnologia |
|---|---|
| Bot | python-telegram-bot v22 (webhook dentro da API) |
| Agente IA | Agno + Groq (`GROQ_MODEL`, padrão `openai/gpt-oss-120b`) |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Banco | Supabase (PostgreSQL) |
| Auth | Supabase Auth (JWT via JWKS, chaves ES256) + JWT próprio do bot (HS256) |
| Frontend | Next.js, Tailwind, shadcn/ui |
| Deploy | Render (API + bot, um serviço) + Vercel (frontend) |

## Estrutura do repositório

```
backend/
  app/          # FastAPI: rotas, auth, config, database
  agent/        # Agente Agno (bot.py, tools.py, prompts.py, history.py)
  core/         # Núcleo de conversa independente de canal (rate limit, alertas)
  tgbot/        # Adaptador Telegram: handlers, runner (polling) e webhook
  wabot/        # Adaptador WhatsApp (Cloud API): webhook, roteador de texto e envio
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
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Crie um `.env` a partir de `.env.example`:

| Variável | Uso |
|---|---|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | anon key (pública), usada com o JWT do usuário |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role ou `sb_secret_...`. Só no backend, nunca no frontend |
| `SUPABASE_JWT_SECRET` | secret JWT legado do Supabase; o bot assina os tokens dos usuários com ele |
| `TELEGRAM_BOT_TOKEN` | token do @BotFather |
| `GROQ_API_KEY` | chave do Groq |
| `GROQ_MODEL` | modelo do agente (padrão `openai/gpt-oss-120b`; o Groq descontinua modelos com frequência) |
| `TELEGRAM_MODE` | `off` (só API), `webhook` (produção) ou `polling` (dev) |
| `PUBLIC_BASE_URL` | URL pública da API (webhook). No Render, usa `RENDER_EXTERNAL_URL` se vazio |
| `TELEGRAM_WEBHOOK_SECRET` | segredo do webhook. Gerar com `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `API_BASE_URL` | onde o bot em polling encontra a API (padrão `http://localhost:8000`) |
| `CORS_ORIGINS` | origens do frontend separadas por vírgula |

Rode as migrations em `backend/supabase/migrations/` (em ordem numérica) no SQL editor do Supabase.

No painel do Supabase, em Authentication > Providers > Email, defina a **senha mínima em 10
caracteres** e, se o plano permitir, ative a proteção contra senhas vazadas. O formulário do
painel já exige 10, mas sem essa configuração alguém poderia se cadastrar direto pela API do
Supabase com uma senha menor.

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

## Usando em um grupo do Telegram

1. Adicione o bot ao grupo da família. Ele manda as instruções.
2. O **dono do grupo financeiro** envia `/vincular` no grupo. Cada grupo financeiro pode ter um
   chat vinculado; `/desvincular` desfaz (os dados continuam salvos).
3. Para falar com o bot no grupo, use uma destas formas:
   - responder a uma mensagem do bot;
   - `/f <mensagem>`, por exemplo `/f gastei R$ 50 no mercado`;
   - mencionar o bot: `@<bot> gastei R$ 50 no mercado`.
4. Quem ainda não participa do grupo financeiro recebe um botão "Aprovar"; só o dono consegue aprovar.

Cada pessoa tem a própria conversa com o bot dentro do grupo: o "sim" de uma pessoa não confirma
o lançamento de outra. Alertas de limite aparecem no grupo.

**Privacy mode.** Por padrão o Telegram só entrega ao bot comandos e respostas às mensagens dele;
a documentação não garante a entrega de menções. Para a menção funcionar sempre, desligue o
privacy mode no @BotFather (`/setprivacy` > Disable). O bot continua ignorando o que não é
dirigido a ele: conversas da família não passam pelo LLM.

## WhatsApp (opcional)

O bot também atende pelo WhatsApp, no privado, com as mesmas funções do Telegram: registrar,
consultar, limites, desfazer, `/convidar` e vínculo com a conta web (`/start <código>`). Os dois
canais funcionam em paralelo e gravam no mesmo grupo financeiro.

Configuração na Meta (Cloud API oficial):

1. Em developers.facebook.com, crie um app do tipo Business e adicione o produto WhatsApp.
2. Registre o número do bot e anote o **Phone number ID**.
3. Gere um **token permanente** (System User no Business Manager, com permissão
   `whatsapp_business_messaging`). O token temporário do painel expira em 24h.
4. Em WhatsApp > Configuration, cadastre o webhook `https://<sua-api>/whatsapp/webhook` com um
   **verify token** escolhido por você e assine o campo `messages`.
5. Copie o **App Secret** (App settings > Basic), usado para validar a assinatura dos webhooks.
6. Preencha no backend `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`,
   `WHATSAPP_VERIFY_TOKEN` e `WHATSAPP_NUMBER` (só dígitos). No frontend,
   `NEXT_PUBLIC_WHATSAPP_NUMBER` mostra o botão "Abrir no WhatsApp" no vínculo de conta.

Sem as quatro primeiras variáveis o canal fica desligado e `/whatsapp/webhook` responde 404.

Limitações:

- **Sem grupos no WhatsApp:** a Groups API da Meta exige Official Business Account e aceita no
  máximo 8 participantes. Cada pessoa da família fala com o bot no privado.
- **Só texto:** áudio, imagem e outros tipos recebem uma mensagem pedindo texto.
- **Janela de 24h e custo:** o bot só responde a mensagens recebidas, então tudo fica dentro da
  janela de atendimento, sem templates. A página oficial de preços indica essas mensagens como
  gratuitas; confira no painel da Meta, porque a política de preços muda com frequência.

## Rodando localmente

### Supabase local (opcional)

Requer Docker. Sobe Postgres, Auth e API em containers e aplica todas as migrations de `backend/supabase/migrations`:

```bash
cd backend
npx supabase start     # primeira vez baixa as imagens
npx supabase status    # URL (http://127.0.0.1:54321), anon key, service_role key, JWT secret
```

Copie os valores para `backend/.env` (`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`SUPABASE_JWT_SECRET`) e `frontend/.env.local`. Studio em http://127.0.0.1:54323.
`npx supabase db reset` recria o banco do zero; `npx supabase stop` desliga.


```bash
# API (TELEGRAM_MODE=off no .env)
cd backend
.venv/bin/uvicorn app.main:app --reload

# Bot em polling, em outro terminal (usa API_BASE_URL)
cd backend
.venv/bin/python -m tgbot.runner

# Frontend
cd frontend
npm run dev
```

Use um **bot de desenvolvimento separado** no @BotFather: o polling apaga o webhook do bot
em que roda, o que derrubaria o bot de produção.

## Deploy

Três projetos na Vercel apontando para o mesmo repositório (Root Directory de cada um):

| Projeto | Root Directory | Domínio de produção |
|---|---|---|
| backend (API + bot Finncy) | `backend` | `backend-phi-three-37.vercel.app` |
| dashboard | `frontend` | `dashboard-chi-swart-23.vercel.app` |
| pedidos (módulo independente) | `pedidos` | `pedidos-zeta-sandy.vercel.app` |

Não deixe o Root Directory vazio: o build tentaria montar mais de um app.

### Backend (`backend/`)

A Vercel injeta `VERCEL=1`, que liga o modo serverless: o webhook do Telegram/WhatsApp é
processado dentro da própria requisição e reentregas são descartadas pela tabela `processed_updates`.

1. Aplicar as migrations (`backend/supabase/migrations/001` a `015`) no Supabase.
2. Variáveis: todas do `backend/.env.example`, com `TELEGRAM_MODE=webhook` (sem `PUBLIC_BASE_URL`)
   e `CORS_ORIGINS` com o domínio do dashboard (sem barra no final).
3. Após o deploy, registrar o webhook (substitui qualquer webhook/polling anterior do bot):

```bash
cd backend
python -m tgbot.set_webhook https://backend-phi-three-37.vercel.app
```

4. WhatsApp (se usado): webhook da Meta em `https://backend-phi-three-37.vercel.app/whatsapp/webhook`.

### Dashboard (`frontend/`)

Variáveis: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
`NEXT_PUBLIC_API_URL` (URL do backend) e `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME`. Variáveis
`NEXT_PUBLIC_*` entram no build: depois de alterar, faça Redeploy.

### Render (alternativa)

O `render.yaml` continua válido para o backend: web service sempre ligado
(`TELEGRAM_MODE=webhook` + `PUBLIC_BASE_URL`), com a fila em background. No plano free o
serviço hiberna e a primeira mensagem depois disso demora.

## Testes

```bash
cd backend
.venv/bin/pytest
```

A suíte não precisa de `.env` (os valores padrão estão em `tests/conftest.py`).

## Status do projeto

Ver [`PENDENTE.md`](PENDENTE.md) para pendências em andamento e débitos técnicos conhecidos.

## Segurança

Ver [`SECURITY.md`](SECURITY.md) para o levantamento de vulnerabilidades conhecidas e o que já foi corrigido.
