-- Continuacao da 007/008: ultimo passo do consumo do codigo de vinculo
-- (auth_link.py) e gravar o telegram_id na linha public.users da conta web,
-- via role anon. Faltava grant/policy de UPDATE para anon -- 002/003 so
-- concederam SELECT e INSERT, e a 008 adicionou DELETE.

CREATE POLICY "users_bot_update" ON public.users
  FOR UPDATE TO anon USING (true) WITH CHECK (true);

GRANT UPDATE ON public.users TO anon;
