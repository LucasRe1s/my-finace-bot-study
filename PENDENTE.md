# O que falta — my-finance-bot

> Atualizado em 07/10/2026. Fases 1 (producao), 2 (nucleo de canal) e 3 (familia no privado) implementadas no codigo. Roteiro completo das proximas fases em
> [`specs/2026-10-07-producao-e-familia-design.md`](specs/2026-10-07-producao-e-familia-design.md).

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
| SEC-01 | Client de servico no backend + migration 011 remove todo acesso do role anon | Completo |
| SEC-02 | Aceite de convite atomico via servico; remove `invites_accept_update` e `group_members_insert_self` | Completo |
| Bot na API | Webhook `POST /telegram/webhook` no lifespan do FastAPI; tools chamam a API em processo | Completo |
| Vinculo Telegram | Endpoint publico `/auth/telegram-link` removido; bot chama o servico direto | Completo |
| CORS-01 | Origens via `CORS_ORIGINS` | Completo |
| OPENAI-01 | `OPENAI_API_KEY` removida das settings | Completo |
| Deploy (codigo) | `render.yaml` com um unico web service | Completo |
| FRONT-01 | `apiFetch` mostra so o `detail` da API em vez do JSON cru | Completo |
| Fase 2 | `user_identities` (migration 012), nucleo `core/` independente de canal, Telegram como adaptador | Completo |
| Fase 2 | Rate limit por usuario no bot (30 mensagens / 10 min) | Completo |
| Fase 3 | `/convidar` e `/start join_<token>`: familia entra no grupo so pelo Telegram (migration 013: convite com validade de 7 dias e email opcional) | Completo |
| Fase 3 | Nomes de membros e autor de cada transacao (API, bot e painel) | Completo |
| Fase 3 | Desfazer o ultimo lancamento proprio (10 min) | Completo |
| Fase 2 | Vinculo de conta: transfere posse do grupo antes de apagar a conta so-bot (evita cascade), descarta historico duplicado, recusa contas em grupos diferentes, codigo de uso unico atomico | Completo |

---

## Pendente: proximo passo

### DEPLOY-01: executar o deploy

Passo a passo na secao "Deploy" do [`README.md`](README.md). Atencao a ordem: a migration 011
so pode ser aplicada depois que o backend novo (com `SUPABASE_SERVICE_ROLE_KEY`) estiver no ar.

### Fases 4 a 6

Ver [`specs/2026-10-07-producao-e-familia-design.md`](specs/2026-10-07-producao-e-familia-design.md):
bot em grupo do Telegram, WhatsApp e debitos tecnicos.

---

## Debitos tecnicos

| Origem | Descricao |
|---|---|
| P1-T5 | `?month=` sem validacao de formato — ValueError vira 500 |
| P3-T2 | `getSession()` no servidor — trocar por `getUser()` |
| P3-T2 | Auth callback sem redirect quando `code` ausente |
| ~~DEBUG-01~~ | ~~Remover `/debug/token` endpoint antes do deploy~~ — feito |
| SEC-03 | Senha minima de 6 caracteres no signup via convite |
| Fase 2 | Remover `users.telegram_id` e `_adopt_legacy_telegram_user` quando todos os usuarios tiverem identidade |
