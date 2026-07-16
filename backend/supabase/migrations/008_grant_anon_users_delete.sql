-- Continuacao da 007: ao consumir o codigo de vinculo (auth_link.py), depois
-- de migrar group_members/transactions/conversations para a conta web, o bot
-- (role anon) precisa apagar a linha antiga de public.users (a identidade
-- "so-bot" que ficou orfa). Faltava grant/policy de DELETE para anon --
-- so SELECT e INSERT foram concedidos em 002/003.

CREATE POLICY "users_bot_delete" ON public.users
  FOR DELETE TO anon USING (true);

GRANT DELETE ON public.users TO anon;
