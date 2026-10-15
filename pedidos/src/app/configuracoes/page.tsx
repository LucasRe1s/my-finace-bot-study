import { Shell } from "@/components/nav";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";
import { formatDateTime } from "@/lib/format";
import { generateLinkCodeAction } from "./actions";

export default async function ConfiguracoesPage() {
  await requireUser();
  const settings = await getDeps().repo.getSettings();
  const code =
    settings.link_code &&
    settings.link_code_expires_at &&
    new Date(settings.link_code_expires_at) > new Date()
      ? settings.link_code
      : null;
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;

  return (
    <Shell title="Configurações">
      <section className="card space-y-3">
        <h2 className="font-medium">Contato da granja no Telegram</h2>
        <p className="text-sm">
          {settings.granja_chat_id ? (
            <span className="text-emerald-700">Vinculado. Os pedidos estão sendo enviados para esse contato.</span>
          ) : (
            <span className="text-red-700">Nenhum contato vinculado. Os pedidos não serão enviados.</span>
          )}
        </p>

        {code ? (
          <div className="space-y-2 rounded-md bg-slate-50 p-3 text-sm">
            <p>Peça para o contato da granja enviar ao bot a mensagem:</p>
            <p className="font-mono text-lg">/start {code}</p>
            {botUsername && (
              <p>
                Ou abrir este link no celular:{" "}
                <a className="underline" href={`https://t.me/${botUsername}?start=${code}`}>
                  t.me/{botUsername}?start={code}
                </a>
              </p>
            )}
            <p className="text-slate-500">Válido até {formatDateTime(settings.link_code_expires_at!)}.</p>
          </div>
        ) : null}

        <form action={generateLinkCodeAction}>
          <button className="btn-secondary">
            {settings.granja_chat_id ? "Trocar contato (gerar código)" : "Gerar código de vínculo"}
          </button>
        </form>
      </section>
    </Shell>
  );
}
