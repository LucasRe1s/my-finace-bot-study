// Registra o webhook do bot de pedidos no Telegram.
// Uso: npm run telegram:set-webhook -- https://seu-app.vercel.app
const [baseUrl] = process.argv.slice(2);
const token = process.env.TELEGRAM_BOT_TOKEN;
const secret = process.env.TELEGRAM_WEBHOOK_SECRET;

if (!baseUrl || !token || !secret) {
  console.error(
    "Uso: npm run telegram:set-webhook -- https://seu-app.vercel.app\n" +
      "Requer TELEGRAM_BOT_TOKEN e TELEGRAM_WEBHOOK_SECRET no .env.local",
  );
  process.exit(1);
}

const url = `${baseUrl.replace(/\/$/, "")}/api/telegram/webhook`;
const res = await fetch(`https://api.telegram.org/bot${token}/setWebhook`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    url,
    secret_token: secret,
    allowed_updates: ["message", "callback_query"],
    drop_pending_updates: true,
  }),
});
const json = await res.json();
console.log(json.ok ? `Webhook registrado: ${url}` : `Erro: ${json.description}`);
process.exit(json.ok ? 0 : 1);
