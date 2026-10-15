import { redirect } from "next/navigation";
import { createAuthClient } from "./supabase-server";

/** Garante usuário logado (valida o token no Supabase); senão manda para /login. */
export async function requireUser(): Promise<{ id: string; email: string }> {
  const supabase = await createAuthClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  return { id: user.id, email: user.email ?? "" };
}
