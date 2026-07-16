"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { getInvitePreview, acceptInvite, type InvitePreview } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Mode = "signup" | "login";

export default function ConvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const supabase = createSupabaseBrowserClient();

  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("signup");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "confirm-email">(
    "idle"
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    getInvitePreview(token)
      .then(setPreview)
      .catch(() =>
        setPreviewError(
          "Convite inválido ou já utilizado. Peça um novo link para quem te convidou."
        )
      );
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!preview) return;
    setStatus("loading");
    setErrorMsg(null);

    const { data, error } =
      mode === "signup"
        ? await supabase.auth.signUp({ email: preview.email, password })
        : await supabase.auth.signInWithPassword({
            email: preview.email,
            password,
          });

    if (error) {
      setErrorMsg(error.message);
      setStatus("idle");
      return;
    }

    if (!data.session) {
      setStatus("confirm-email");
      return;
    }

    try {
      await acceptInvite(data.session.access_token, token);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Erro ao aceitar convite."
      );
      setStatus("idle");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center text-xl">
            Convite para o Assistente Financeiro
          </CardTitle>
        </CardHeader>
        <CardContent>
          {previewError && (
            <p className="text-sm text-red-600">{previewError}</p>
          )}

          {!previewError && !preview && (
            <p className="text-sm text-gray-500">Carregando convite...</p>
          )}

          {preview && status === "confirm-email" && (
            <p className="text-sm text-gray-600">
              Enviamos um email de confirmação para <strong>{preview.email}</strong>.
              Confirme sua conta e volte nesse mesmo link pra entrar no grupo
              &quot;{preview.group_name}&quot;.
            </p>
          )}

          {preview && status !== "confirm-email" && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <p className="text-sm text-gray-600">
                Você foi convidado para o grupo{" "}
                <strong>{preview.group_name}</strong>.
              </p>

              <div className="space-y-1">
                <Label>Email</Label>
                <Input type="email" value={preview.email} disabled readOnly />
              </div>

              <div className="space-y-1">
                <Label htmlFor="password">
                  {mode === "signup" ? "Crie uma senha" : "Senha"}
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  autoComplete={
                    mode === "signup" ? "new-password" : "current-password"
                  }
                />
              </div>

              {errorMsg && <p className="text-sm text-red-600">{errorMsg}</p>}

              <Button type="submit" className="w-full" disabled={status === "loading"}>
                {status === "loading"
                  ? "Entrando..."
                  : mode === "signup"
                    ? "Criar conta e entrar no grupo"
                    : "Entrar e entrar no grupo"}
              </Button>

              <button
                type="button"
                className="text-xs text-gray-500 underline w-full text-center"
                onClick={() =>
                  setMode(mode === "signup" ? "login" : "signup")
                }
              >
                {mode === "signup"
                  ? "Já tenho conta, entrar"
                  : "Ainda não tenho conta, criar"}
              </button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
