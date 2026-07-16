"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { sendInvite } from "@/lib/api";

type InviteFormProps = {
  token: string;
};

export function InviteForm({ token }: InviteFormProps) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">(
    "idle"
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMsg(null);

    try {
      const invite = await sendInvite(token, email);
      setInviteToken(invite.token);
      setStatus("success");
      setEmail("");
      setCopied(false);
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Erro ao enviar convite."
      );
    }
  }

  async function handleCopyLink() {
    if (!inviteToken) return;
    const link = `${window.location.origin}/convite/${inviteToken}`;
    await navigator.clipboard.writeText(link);
    setCopied(true);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="invite-email">Email do familiar</Label>
        <Input
          id="invite-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email@exemplo.com"
          required
          disabled={status === "loading"}
        />
      </div>
      {status === "success" && inviteToken && (
        <div className="space-y-1 rounded-md bg-gray-50 p-3">
          <p className="text-sm text-green-600">
            Convite criado. Não enviamos email — copie o link e mande você
            mesmo (WhatsApp, etc.):
          </p>
          <div className="flex items-center gap-2">
            <code className="text-xs text-gray-600 break-all">
              {typeof window !== "undefined"
                ? `${window.location.origin}/convite/${inviteToken}`
                : `/convite/${inviteToken}`}
            </code>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={handleCopyLink}
            >
              {copied ? "Copiado!" : "Copiar"}
            </Button>
          </div>
        </div>
      )}
      {status === "error" && errorMsg && (
        <p className="text-sm text-red-600">{errorMsg}</p>
      )}
      <Button type="submit" disabled={status === "loading"} className="w-full">
        {status === "loading" ? "Enviando..." : "Enviar Convite"}
      </Button>
    </form>
  );
}
