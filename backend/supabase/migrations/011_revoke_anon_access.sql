-- SEC-01 e SEC-02 (ver SECURITY.md).
--
-- As migrations 002 a 010 deram ao role anon policies USING (true) para o bot
-- operar sem sessao de usuario. Como a anon key e publica (fica no bundle do
-- frontend), isso expunha todas as tabelas. Agora o backend usa a service_role
-- key para essas operacoes (app/database.py::get_service_supabase), entao o
-- role anon perde todo acesso as tabelas do app.
--
-- Tambem remove:
-- - invites_accept_update (001): qualquer autenticado marcava qualquer convite
--   como aceito. O aceite agora roda como servico depois de validar o token.
-- - group_members_insert_self (001): qualquer autenticado se inseria em
--   qualquer grupo. O insert do dono ao criar grupo segue coberto por
--   group_members_owner_all (005); o do convidado roda como servico.
--
-- Aplicar SO depois que o backend com SUPABASE_SERVICE_ROLE_KEY estiver no ar:
-- o codigo anterior depende dessas policies.

DROP POLICY IF EXISTS "users_bot_read" ON public.users;
DROP POLICY IF EXISTS "users_bot_insert" ON public.users;
DROP POLICY IF EXISTS "users_bot_update" ON public.users;
DROP POLICY IF EXISTS "users_bot_delete" ON public.users;
DROP POLICY IF EXISTS "conversations_bot_all" ON public.conversations;
DROP POLICY IF EXISTS "telegram_link_codes_bot_all" ON public.telegram_link_codes;
DROP POLICY IF EXISTS "group_members_bot_all" ON public.group_members;
DROP POLICY IF EXISTS "transactions_bot_all" ON public.transactions;
DROP POLICY IF EXISTS "invites_bot_select" ON public.invites;
DROP POLICY IF EXISTS "groups_bot_select" ON public.groups;

DROP POLICY IF EXISTS "invites_accept_update" ON public.invites;
DROP POLICY IF EXISTS "group_members_insert_self" ON public.group_members;

REVOKE ALL ON public.users FROM anon;
REVOKE ALL ON public.conversations FROM anon;
REVOKE ALL ON public.groups FROM anon;
REVOKE ALL ON public.group_members FROM anon;
REVOKE ALL ON public.transactions FROM anon;
REVOKE ALL ON public.category_limits FROM anon;
REVOKE ALL ON public.invites FROM anon;
REVOKE ALL ON public.telegram_link_codes FROM anon;
