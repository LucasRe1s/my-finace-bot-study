# Pedidos

Web para registrar pedidos de mercados e enviá-los ao contato da granja por um bot do Telegram. A granja responde com botões (Aceitar, Recusar, Saiu para entrega) e o status aparece na web.

Módulo independente: não usa nada fora desta pasta. Design em `../docs/superpowers/specs/2026-10-14-pedidos-design.md`.

## Stack

Next.js 16 (App Router), Supabase (Postgres + Auth), Bot API do Telegram via webhook, Vercel.

## Configuração

### 1. Supabase

1. No SQL editor do projeto, rode `supabase/migrations/001_pedidos_schema.sql`.
2. Em **Authentication → Users**, crie os usuários da equipe (email e senha). Desative o cadastro público em **Authentication → Sign In / Providers** (só quem vocês criarem consegue entrar).
3. Em **Project Settings → API Keys**, copie a URL, a anon key e a service role key.

### 2. Bot do Telegram

1. No [@BotFather](https://t.me/BotFather), `/newbot` e copie o token.
2. Gere um segredo para o webhook: `openssl rand -hex 32`.

### 3. Variáveis

Copie `.env.local.example` para `.env.local` e preencha. As mesmas variáveis vão para o projeto na Vercel. `SUPABASE_SERVICE_ROLE_KEY` e `TELEGRAM_BOT_TOKEN` são secretas e só existem no servidor.

## Rodando localmente

```bash
npm install
npm run dev     # http://localhost:3000
npm test        # testes (Vitest)
```

O webhook precisa de URL pública. Para testar os botões localmente, exponha a porta 3000 (ex.: `cloudflared tunnel --url http://localhost:3000`) e registre o webhook com essa URL.

## Deploy (Vercel)

1. Importe o repositório na Vercel como um projeto novo, com **Root Directory = `pedidos`**. O dashboard do assessor é outro projeto Vercel apontando para o mesmo repositório com Root Directory = `frontend`. O `vercel.json` de cada pasta faz a Vercel pular o build quando o commit não mexe naquela pasta.
2. Cadastre as variáveis de ambiente.
3. Após o deploy, registre o webhook:

```bash
npm run telegram:set-webhook -- https://seu-app.vercel.app
```

4. Na web, em **Configurações**, gere o código de vínculo e peça ao contato da granja para enviar `/start CODIGO` ao bot.

## Status do pedido

| Status | Quem muda | Como |
|---|---|---|
| enviado | sistema | ao criar o pedido |
| erro_envio | sistema | falha no envio ou granja não vinculada (web mostra "Reenviar") |
| aceito / recusado | granja | botões no Telegram |
| em_entrega | granja | botão "Saiu para entrega" |
| entregue | web | "Marcar como entregue" |
| cancelado | web | "Cancelar pedido" (antes de entregue) |
