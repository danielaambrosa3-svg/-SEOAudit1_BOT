import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in Railway's Variables tab or in your local .env file."
        )
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "")
RAPIDAPI_ENDPOINT = os.getenv("RAPIDAPI_ENDPOINT", "")
RAPIDAPI_DOMAIN_PARAM = os.getenv("RAPIDAPI_DOMAIN_PARAM", "domain")

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "30"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
