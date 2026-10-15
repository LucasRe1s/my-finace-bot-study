# Módulo de Pedidos (granja) — Design

> Data: 14/10/2026. Status: aguardando revisão.

## Objetivo

Uma web simples onde a equipe registra pedidos de mercados (cliente em texto livre + itens em caixas). Cada pedido é enviado automaticamente por um bot do Telegram ao contato da granja, que responde com botões. O status do pedido é acompanhado na web.

Módulo isolado dentro deste repositório (`pedidos/`), sem dependência do assessor financeiro, para ser movido para um repositório próprio no futuro.

## Escopo

**Dentro:**
- Login por email/senha (Supabase Auth); todos os usuários têm o mesmo acesso.
- Cadastro de produtos: nome, descrição, unidades por caixa, ativo/inativo.
- Novo pedido: nome do mercado (texto livre), itens (produto + nº de caixas), observação opcional.
- Lista de pedidos com filtro por status; detalhe com itens e histórico.
- Envio ao Telegram da granja com botões; atualização de status pelos botões.
- Na web: marcar Entregue, Cancelar, Reenviar (quando o envio falhou).
- Vínculo do contato da granja ao bot por código de uso único.

**Fora (por enquanto):** cadastro de clientes, papéis de usuário, relatórios, pedido por áudio/Telegram, múltiplas granjas.

## Arquitetura e hospedagem

- Next.js (App Router, TypeScript), projeto Vercel próprio (plano Hobby; risco dos termos de uso comercial aceito pelo usuário em 14/10/2026).
- Rotas de servidor do Next (Server Actions / Route Handlers); sem FastAPI e sem processo sempre ligado.
- Supabase próprio (projeto `vawbaxtzclbaofyzwbsi`), separado do assessor.
- Bot do Telegram próprio (token diferente do `@finncyBot`), operando por **webhook**.

```
pedidos/
├── src/app/login
├── src/app/pedidos            lista + filtro
├── src/app/pedidos/novo       criar pedido
├── src/app/pedidos/[id]       detalhe, histórico, ações
├── src/app/produtos           cadastro
├── src/app/configuracoes      vínculo da granja
├── src/app/api/telegram/webhook
├── src/lib/status.ts          regras de transição (função pura)
├── src/lib/telegram.ts        envio/edição de mensagem, teclados
├── src/lib/supabase/          clientes server (service role) e auth
└── supabase/migrations/
```

## Dados

| Tabela | Campos |
|---|---|
| `products` | id uuid, name, description, units_per_box int > 0, active bool, created_at |
| `orders` | id uuid, number serial (exibido como #42), customer_name, notes, status, telegram_message_id bigint null, created_by uuid (auth.users), created_at, updated_at |
| `order_items` | id, order_id, product_id, product_name, units_per_box, boxes int > 0 |
| `order_events` | id, order_id, from_status null, to_status, actor text (`web:<email>` ou `granja`), created_at |
| `settings` | linha única: granja_chat_id bigint null, link_code text null, link_code_expires_at |

- `order_items` copia `product_name` e `units_per_box` no momento do pedido; editar um produto não altera pedidos antigos. Produtos são desativados, nunca apagados.
- **Segurança:** RLS habilitado em todas as tabelas e nenhuma policy para `anon` ou `authenticated`. Todo acesso a dados passa pelo servidor com a service role key, após checar a sessão do usuário (ou, no webhook, o secret e o chat da granja). A service role key nunca vai para o navegador.

## Status

```
erro_envio ──(reenviar)──> enviado
enviado ──(granja: aceitar)──> aceito
enviado ──(granja: recusar)──> recusado
aceito ──(granja: saiu para entrega)──> em_entrega
em_entrega ──(web: entregue)──> entregue
enviado | aceito | em_entrega | erro_envio ──(web: cancelar)──> cancelado
```

`recusado`, `entregue` e `cancelado` são finais. A tabela de transições permitidas (incluindo quem pode disparar cada uma: `web` ou `granja`) vive em `lib/status.ts` e é usada pela web e pelo webhook. Toda transição aplicada grava um `order_events`. A atualização no banco é condicional ao status atual (`update ... where status = <esperado>`) para evitar corrida entre cliques.

## Fluxos

**Vincular a granja:** em Configurações, gerar código (válido por 24h). O contato envia `/start CODIGO` ao bot; o webhook confere o código, grava `granja_chat_id`, invalida o código e responde confirmando. Um novo vínculo substitui o anterior.

**Criar pedido:** grava pedido + itens (status `enviado`) e envia a mensagem:

```
Novo pedido #42
Cliente: Mercado X
- 10 cx Ovo branco grande (30 un/cx)
- 5 cx Ovo vermelho médio (30 un/cx)
Obs.: entregar até sexta

[✅ Aceitar] [❌ Recusar]
```

Guarda o `telegram_message_id`. Se não houver granja vinculada ou o Telegram falhar, o pedido fica `erro_envio` e a web mostra o motivo e o botão Reenviar.

**Botões da granja:** `callback_data` = `<acao>:<order_id>`. O webhook valida o header `X-Telegram-Bot-Api-Secret-Token` e se `chat.id == granja_chat_id`, aplica a transição e edita a mensagem (linha "✅ Aceito em 14/10 14:32" + botões do próximo passo; sem botões em status final). Clique inválido ou repetido não altera nada e responde com `answerCallbackQuery` curto ("Pedido já cancelado"). O webhook sempre responde 200 para o Telegram não reenviar.

**Ações da web:** Entregue e Cancelar aplicam a transição e editam a mensagem na granja ("❌ Cancelado pelo escritório", "📦 Entregue"). Falha ao editar a mensagem não desfaz a mudança de status (é só registrada em log).

## Configuração

`.env.local` / Vercel: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (só para Auth), `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`. O registro do webhook (`setWebhook` com `secret_token`) é feito por um script `npm run telegram:set-webhook`.

## Testes

- Vitest: `lib/status.ts` (todas as transições válidas e inválidas, por ator), formatação da mensagem e teclados, handler do webhook (secret errado → 401; chat errado → ignorado; clique duplicado → sem mudança; `/start` com código válido/expirado).
- Server actions/rotas com Supabase e Telegram mockados (criar pedido com falha de envio → `erro_envio`).
- Teste manual ponta a ponta com o bot real antes do deploy.
