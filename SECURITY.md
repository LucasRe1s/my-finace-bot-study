# Segurança: my-finance-bot

Levantamento das vulnerabilidades e pontos fracos conhecidos deste projeto. É um app pessoal/familiar, não um produto multi-tenant com terceiros desconhecidos. Mesmo assim, vale registrar o que está frágil, principalmente antes de um deploy público.

> Atualizado em 07/10/2026, após a Fase 1 (`specs/2026-10-07-plan-4-producao.md`).

## Médio

### 1. Secrets de alto privilégio no backend

- `SUPABASE_SERVICE_ROLE_KEY` bypassa todo o RLS. Fica só no backend (Render), nunca no frontend nem em `NEXT_PUBLIC_*`. Usada apenas por `app/database.py::get_service_supabase()`, nas operações do sistema listadas na spec (bot, preview e aceite de convite).
- `SUPABASE_JWT_SECRET` é usado pelo bot (`_generate_user_token`) para emitir tokens em nome de qualquer `user_id`. Se vazar, dá pra forjar um token válido para qualquer usuário.
- `TELEGRAM_WEBHOOK_SECRET` impede que terceiros injetem updates falsos em `POST /telegram/webhook`. A rota recusa tudo (403) quando ele não está configurado.

Os três precisam ser tratados como credenciais de altíssimo privilégio e rotacionados se houver suspeita de vazamento.

### 2. Código de vínculo do Telegram pode ser usado por quem o vir

O vínculo confia que quem manda `/start <código>` no bot é a mesma pessoa que gerou o código no site. Quem vê o código (print de tela, mensagem encaminhada) consegue vincular a própria conta Telegram a ele dentro da janela de 10 minutos. O código é de uso único, e o endpoint público `POST /auth/telegram-link` não existe mais (o bot chama o serviço direto, dentro da API), então não dá para testar códigos por HTTP.

### 3. Senha mínima de 6 caracteres no cadastro via convite

`frontend/src/app/convite/[token]/page.tsx` pede `minLength={6}`. Fraco para uma senha de acesso a dados financeiros. Planejado na Fase 6: mínimo de 10 caracteres e checagem de senha vazada no Supabase Auth.

## Baixo / observações

- Não há rate limiting em `/auth/telegram-link-code` (baixo impacto, só spam de linhas na tabela) nem por usuário no bot (planejado na Fase 2, para proteger a cota do Groq).
- `invites.email` é validado como `str` livre, não `EmailStr`.
- `?month=` em `/transactions` e `/summary` não valida formato: entrada malformada vira 500 em vez de 422.

## Já corrigido

- ~~**Role `anon` com acesso amplo (era crítico).**~~ As migrations 002 a 010 davam ao `anon` policies `USING (true)` em `users`, `conversations`, `group_members`, `transactions`, `invites`, `groups` e `telegram_link_codes`, e a anon key é pública no bundle do frontend. Corrigido: o backend usa `get_service_supabase()` para as operações sem usuário, e a migration `011_revoke_anon_access.sql` remove todas essas policies e faz `REVOKE ALL` do `anon` nas tabelas do app. `tests/test_migrations.py` falha se alguma policy `TO anon` antiga não for removida.
- ~~**`invites_accept_update` aceitava qualquer convite.**~~ Policy removida na 011. `POST /groups/accept` agora reivindica o convite com um único `UPDATE ... WHERE token = ? AND accepted_at IS NULL` via client de serviço (só um aceite vence) e recusa com 409 quem já está em um grupo.
- ~~**`group_members_insert_self` deixava qualquer autenticado entrar em qualquer grupo.**~~ Policy removida na 011. O insert do dono ao criar grupo segue coberto por `group_members_owner_all`; o do convidado roda como serviço depois de validar o token.
- ~~**CORS liberado para qualquer origem.**~~ Agora `allow_origins` vem de `CORS_ORIGINS`.
- ~~`/debug/token` expunha o payload do JWT sem verificar assinatura.~~ Endpoint removido.
- ~~Backend validava só HS256, rejeitando os tokens ES256 do Supabase.~~ Verificação via JWKS.
