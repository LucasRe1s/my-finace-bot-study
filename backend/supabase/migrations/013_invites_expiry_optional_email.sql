-- Fase 3: convite pelo bot do Telegram.
--
-- email opcional: o convite gerado no bot nao tem email (o link vai direto
-- para o familiar). Validado como email na API quando informado.
-- expires_at: convites passam a valer 7 dias. Antes nao expiravam, e um link
-- encaminhado ficaria valido para sempre. Convites antigos ganham 7 dias a
-- partir da aplicacao desta migration.

ALTER TABLE public.invites ALTER COLUMN email DROP NOT NULL;
ALTER TABLE public.invites ADD COLUMN expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days');
