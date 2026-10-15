"use server";

import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";
import { generateLinkCode } from "@/lib/webhook";

const CODE_TTL_MS = 24 * 60 * 60 * 1000;

export async function generateLinkCodeAction() {
  await requireUser();
  await getDeps().repo.saveSettings({
    link_code: generateLinkCode(),
    link_code_expires_at: new Date(Date.now() + CODE_TTL_MS).toISOString(),
  });
  revalidatePath("/configuracoes");
}
