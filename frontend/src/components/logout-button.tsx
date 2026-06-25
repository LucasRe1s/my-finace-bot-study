"use client";

import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function LogoutButton() {
  const supabase = createSupabaseBrowserClient();
  const router = useRouter();

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <Button variant="outline" size="sm" onClick={handleLogout}>
      Sair
    </Button>
  );
}
