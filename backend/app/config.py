from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    # service_role bypassa RLS: so no backend, nunca no frontend.
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str
    telegram_bot_token: str
    groq_api_key: str = ""

    # "off": API sem bot (testes, dev so da API); "webhook": bot dentro da API
    # (producao); "polling": bot separado via `python -m tgbot.runner` (dev).
    telegram_mode: str = "off"
    # URL publica da API, usada para registrar o webhook. No Render, cai para a
    # RENDER_EXTERNAL_URL injetada automaticamente.
    public_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"),
    )
    telegram_webhook_secret: str = ""
    # So no modo polling: onde o bot separado encontra a API.
    api_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"

    # WhatsApp Cloud API. O canal fica desligado se faltar qualquer um dos quatro primeiros.
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""
    # Numero do bot so com digitos (DDI + DDD + numero), para links wa.me.
    whatsapp_number: str = ""
    whatsapp_graph_version: str = "v26.0"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def whatsapp_enabled(self) -> bool:
        return all((
            self.whatsapp_access_token,
            self.whatsapp_phone_number_id,
            self.whatsapp_app_secret,
            self.whatsapp_verify_token,
        ))


settings = Settings()
