"use server";

import { redirect } from "next/navigation";
import { createAuthClient } from "@/lib/supabase-server";

export async function signIn(_prev: string | null, formData: FormData): Promise<string | null> {
  const supabase = await createAuthClient();
  const { error } = await supabase.auth.signInWithPassword({
    email: String(formData.get("email") ?? ""),
    password: String(formData.get("password") ?? ""),
  });
  if (error) return "Email ou senha incorretos.";
  redirect("/pedidos");
}

export async function signOut() {
  const supabase = await createAuthClient();
  await supabase.auth.signOut();
  redirect("/login");
}
