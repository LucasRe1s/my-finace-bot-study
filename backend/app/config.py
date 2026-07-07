from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    supabase_jwt_secret: str
    telegram_bot_token: str
    openai_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
