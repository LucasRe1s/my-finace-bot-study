import { timingSafeEqual } from "node:crypto";
import { getDeps } from "@/lib/deps";
import { handleTelegramUpdate } from "@/lib/webhook";

function sameSecret(received: string, expected: string): boolean {
  const a = Buffer.from(received);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function POST(request: Request) {
  const expected = process.env.TELEGRAM_WEBHOOK_SECRET;
  const received = request.headers.get("x-telegram-bot-api-secret-token") ?? "";
  if (!expected || !sameSecret(received, expected)) {
    return new Response("Unauthorized", { status: 401 });
  }

  // Sempre 200 daqui em diante: senão o Telegram reenvia o mesmo update.
  try {
    const update = await request.json();
    await handleTelegramUpdate({ ...getDeps(), now: () => new Date() }, update);
  } catch (err) {
    console.error("[pedidos] erro no webhook do Telegram:", err);
  }
  return Response.json({ ok: true });
}
