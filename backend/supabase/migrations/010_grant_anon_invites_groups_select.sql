-- GET /groups/invite/{token} e uma pagina publica (quem recebeu o convite
-- ainda nao tem conta) que precisa ler o convite e o nome do grupo antes do
-- login/signup -- roda como role anon. Faltavam grants/policies de SELECT
-- para anon em invites e groups.

CREATE POLICY "invites_bot_select" ON public.invites
  FOR SELECT TO anon USING (true);

CREATE POLICY "groups_bot_select" ON public.groups
  FOR SELECT TO anon USING (true);

GRANT SELECT ON public.invites TO anon;
GRANT SELECT ON public.groups TO anon;
