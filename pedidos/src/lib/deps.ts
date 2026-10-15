import type { Deps } from "./orders";
import { SupabaseRepo } from "./repo-supabase";
import { createAdminClient, requireEnv } from "./supabase-server";
import { createTelegramClient } from "./telegram";

/** Dependências reais (Supabase service role + Bot API). Só no servidor. */
export function getDeps(): Deps {
  return {
    repo: new SupabaseRepo(createAdminClient()),
    tg: createTelegramClient(requireEnv("TELEGRAM_BOT_TOKEN")),
  };
}
