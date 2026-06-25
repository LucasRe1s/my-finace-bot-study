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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMsg(null);

    try {
      await sendInvite(token, email);
      setStatus("success");
      setEmail("");
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Erro ao enviar convite."
      );
    }
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
      {status === "success" && (
        <p className="text-sm text-green-600">Convite enviado com sucesso.</p>
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
