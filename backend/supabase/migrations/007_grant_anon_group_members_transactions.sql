-- O vinculo de conta Telegram (auth_link.py::consume_telegram_link_code) roda
-- como role anon (o bot ainda nao tem um usuario para gerar um JWT quando
-- recebe /start <codigo>) e precisa migrar group_members/transactions de uma
-- identidade "so-bot" antiga para a conta web, quando aplicavel. Faltavam os
-- grants/policies pra anon nessas duas tabelas -- so users/conversations
-- tinham (002_bot_auth.sql), causando "permission denied for table
-- group_members" (42501) ao consumir o codigo.

CREATE POLICY "group_members_bot_all" ON public.group_members
  FOR ALL TO anon USING (true) WITH CHECK (true);

CREATE POLICY "transactions_bot_all" ON public.transactions
  FOR ALL TO anon USING (true) WITH CHECK (true);

GRANT SELECT, UPDATE ON public.group_members TO anon;
GRANT SELECT, UPDATE ON public.transactions TO anon;
