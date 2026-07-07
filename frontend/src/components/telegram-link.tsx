import { Button } from "@/components/ui/button";

export function TelegramLink() {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? "";
  return (
    <a
      href={`https://t.me/${botUsername}`}
      target="_blank"
      rel="noopener noreferrer"
    >
      <Button variant="outline" size="sm">
        Abrir no Telegram
      </Button>
    </a>
  );
}
