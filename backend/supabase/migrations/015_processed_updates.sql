-- Deploy serverless (Vercel): ids de updates do Telegram/WhatsApp ja processados.
-- Cada invocacao pode rodar numa instancia diferente, entao a deduplicacao de
-- reentregas precisa ficar no banco. Chave: "telegram:<update_id>" ou
-- "whatsapp:<wamid>". Escrita so pelo backend (service_role). Aditiva.

CREATE TABLE public.processed_updates (
  key TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX processed_updates_created_at_idx ON public.processed_updates (created_at);

ALTER TABLE public.processed_updates ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.processed_updates FROM anon, authenticated;

-- Limpeza opcional (rodar de vez em quando no SQL editor):
-- DELETE FROM public.processed_updates WHERE created_at < now() - interval '7 days';
