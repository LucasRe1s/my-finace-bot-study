-- Fase 2: identidades por canal (Telegram hoje, WhatsApp na Fase 5).
--
-- Substitui public.users.telegram_id. A coluna continua existindo nesta fase:
-- o backend adota usuarios antigos na primeira mensagem
-- (app/services/identities.py::_adopt_legacy_telegram_user) e ela sai numa
-- migration futura.
--
-- Pode ser aplicada antes do deploy do codigo novo: so adiciona.

CREATE TABLE public.user_identities (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('telegram', 'whatsapp')),
  external_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (channel, external_id)
);

CREATE INDEX user_identities_user_id_idx ON public.user_identities (user_id);

ALTER TABLE public.user_identities ENABLE ROW LEVEL SECURITY;

-- Usuario logado ve as proprias identidades (ex.: painel mostrar "Telegram vinculado").
-- Escrita so pelo backend, via service_role.
CREATE POLICY "user_identities_own_select" ON public.user_identities
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

GRANT SELECT ON public.user_identities TO authenticated;
REVOKE ALL ON public.user_identities FROM anon;

INSERT INTO public.user_identities (user_id, channel, external_id)
SELECT id, 'telegram', telegram_id::text
FROM public.users
WHERE telegram_id IS NOT NULL
ON CONFLICT (channel, external_id) DO NOTHING;
