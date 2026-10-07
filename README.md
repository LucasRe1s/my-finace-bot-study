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
- Registrar receitas/despesas em linguagem natural, com confirmação antes de gravar
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
| Agente IA | Agno + Groq (llama-3.3-70b-versatile) |
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
| `TELEGRAM_MODE` | `off` (só API), `webhook` (produção) ou `polling` (dev) |
| `PUBLIC_BASE_URL` | URL pública da API (webhook). No Render, usa `RENDER_EXTERNAL_URL` se vazio |
| `TELEGRAM_WEBHOOK_SECRET` | segredo do webhook. Gerar com `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `API_BASE_URL` | onde o bot em polling encontra a API (padrão `http://localhost:8000`) |
| `CORS_ORIGINS` | origens do frontend separadas por vírgula |

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

Backend e bot são **um único web service** no Render (`render.yaml` na raiz). Frontend na Vercel.

Ordem (a migration 011 só funciona com o código novo no ar, porque o código antigo depende do role `anon`):

1. No Render, criar o serviço pelo Blueprint e preencher as variáveis `sync: false`.
2. Deploy do backend. No log deve aparecer `Bot ativo em modo webhook: https://.../telegram/webhook`.
3. Aplicar `011_revoke_anon_access.sql` no Supabase.
4. Na Vercel: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
   `NEXT_PUBLIC_API_URL` (URL do Render) e `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME`.
5. No Render, `CORS_ORIGINS` com o domínio da Vercel.

Migrations novas depois do primeiro deploy: `012_user_identities.sql`,
`013_invites_expiry_optional_email.sql` e `014_chat_bindings.sql` só adicionam, então podem ser
aplicadas antes do deploy do código que as usa. Usuários antigos (só com `users.telegram_id`)
são adotados automaticamente na primeira mensagem.

No plano free o serviço hiberna sem tráfego; a primeira mensagem depois disso acorda o serviço
e pode demorar. O Telegram reentrega updates que falharam.

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
