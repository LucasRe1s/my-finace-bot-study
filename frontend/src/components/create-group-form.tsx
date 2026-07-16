"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createGroup } from "@/lib/api";

type CreateGroupFormProps = {
  token: string;
};

export function CreateGroupForm({ token }: CreateGroupFormProps) {
  const router = useRouter();
  const [name, setName] = useState("Minha Família");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMsg(null);

    try {
      await createGroup(token, name);
      router.refresh();
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Erro ao criar grupo."
      );
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="group-name">Nome do grupo</Label>
        <Input
          id="group-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Minha Família"
          required
          disabled={status === "loading"}
        />
      </div>
      {status === "error" && errorMsg && (
        <p className="text-sm text-red-600">{errorMsg}</p>
      )}
      <Button type="submit" disabled={status === "loading"} className="w-full">
        {status === "loading" ? "Criando..." : "Criar Grupo"}
      </Button>
    </form>
  );
}
