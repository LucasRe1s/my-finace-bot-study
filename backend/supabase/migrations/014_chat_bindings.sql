-- Fase 4: bot dentro de um grupo do Telegram.
--
-- chat_bindings: liga um chat (grupo do Telegram, e no futuro do WhatsApp) a
-- um grupo financeiro. No maximo um chat por grupo financeiro.
-- group_chat_history: historico do bot por (usuario, chat de grupo), para a
-- confirmacao pendente de uma pessoa nao ser confirmada por outra. O historico
-- do privado continua em conversations (mudar a UNIQUE(user_id) de la
-- quebraria o codigo antigo durante o deploy).
--
-- Escrita e leitura so pelo backend (service_role). Aditiva: pode ser
-- aplicada antes do deploy.

CREATE TABLE public.chat_bindings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  channel TEXT NOT NULL CHECK (channel IN ('telegram', 'whatsapp')),
  chat_id TEXT NOT NULL,
  group_id UUID REFERENCES public.groups(id) ON DELETE CASCADE NOT NULL,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (channel, chat_id),
  UNIQUE (group_id)
);

CREATE TABLE public.group_chat_history (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  chat_key TEXT NOT NULL,
  messages JSONB NOT NULL DEFAULT '[]',
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, chat_key)
);

ALTER TABLE public.chat_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_chat_history ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.chat_bindings FROM anon;
REVOKE ALL ON public.group_chat_history FROM anon;
