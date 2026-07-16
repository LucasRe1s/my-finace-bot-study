-- Remove dependência do auth.users para bot criar usuários diretamente
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_id_fkey;
ALTER TABLE public.users ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- Bot usa chave anon para lookup inicial (antes de ter JWT do usuário)
CREATE POLICY "users_bot_read" ON public.users
  FOR SELECT TO anon USING (true);

CREATE POLICY "users_bot_insert" ON public.users
  FOR INSERT TO anon WITH CHECK (true);

-- Histórico de conversa acessível pelo bot (anon) e pelo usuário autenticado
CREATE POLICY "conversations_bot_all" ON public.conversations
  FOR ALL TO anon USING (true) WITH CHECK (true);
