"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { createTelegramLinkCode } from "@/lib/api";

type TelegramLinkCodeProps = {
  token: string;
};

export function TelegramLinkCodeCard({ token }: TelegramLinkCodeProps) {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? "";
  const [code, setCode] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleGenerate() {
    setStatus("loading");
    setErrorMsg(null);
    try {
      const result = await createTelegramLinkCode(token);
      setCode(result.code);
      setStatus("idle");
      setCopied(false);
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Erro ao gerar código.");
    }
  }

  async function handleCopy() {
    if (!code) return;
    await navigator.clipboard.writeText(`/start ${code}`);
    setCopied(true);
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500">
        Vincule seu Telegram à sua conta para registrar transações por lá e ver
        tudo refletido aqui no painel. Gere um código e abra o link no
        Telegram em até 10 minutos.
      </p>

      {status === "error" && errorMsg && (
        <p className="text-sm text-red-600">{errorMsg}</p>
      )}

      {code ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <p className="text-sm text-gray-600">
              Comando: <span className="font-mono font-semibold">/start {code}</span>
            </p>
            <Button size="sm" variant="ghost" onClick={handleCopy}>
              {copied ? "Copiado!" : "Copiar"}
            </Button>
          </div>
          <p className="text-xs text-gray-400">
            Cole exatamente esse comando (com a barra no início) no chat do bot,
            ou use o botão abaixo.
          </p>
          <a
            href={`https://t.me/${botUsername}?start=${code}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button size="sm">Abrir no Telegram e vincular</Button>
          </a>
        </div>
      ) : (
        <Button
          size="sm"
          variant="outline"
          onClick={handleGenerate}
          disabled={status === "loading"}
        >
          {status === "loading" ? "Gerando..." : "Gerar código"}
        </Button>
      )}
    </div>
  );
}
