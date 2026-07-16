-- Vinculo de conta web <-> Telegram: usuario gera um codigo de uso unico no
-- dashboard e o bot consome esse codigo via /start <codigo>, associando o
-- telegram_id a linha public.users da conta web (em vez de criar uma
-- identidade separada e desconectada, como acontecia hoje).

CREATE TABLE public.telegram_link_codes (
  code TEXT PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ
);

ALTER TABLE public.telegram_link_codes ENABLE ROW LEVEL SECURITY;

-- Usuario autenticado so ve/cria seus proprios codigos
CREATE POLICY "telegram_link_codes_own_select" ON public.telegram_link_codes
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "telegram_link_codes_own_insert" ON public.telegram_link_codes
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Bot (role anon) precisa consultar/consumir o codigo antes de saber a quem
-- ele pertence -- mesmo padrao ja usado em users_bot_read/conversations_bot_all
-- (002_bot_auth.sql) para as demais operacoes do bot.
CREATE POLICY "telegram_link_codes_bot_all" ON public.telegram_link_codes
  FOR ALL TO anon USING (true) WITH CHECK (true);

GRANT SELECT, INSERT ON public.telegram_link_codes TO authenticated;
GRANT SELECT, UPDATE ON public.telegram_link_codes TO anon;
