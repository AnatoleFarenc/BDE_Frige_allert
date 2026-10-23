import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    discord_token: str
    client_id: str
    client_secret: str
    guild_id: int
    channel_id: int
    allowed_role_id: int
    base_url: str
    session_secret: bytes
    web_host: str
    web_port: int
    tz: ZoneInfo
    reminder_times: list[time]
    db_path: str

    @property
    def redirect_uri(self) -> str:
        return f"{self.base_url}/callback"


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")
    return value


def load_config() -> Config:
    load_dotenv()
    tz = ZoneInfo(os.environ.get("TIMEZONE", "Europe/Paris"))
    raw_times = os.environ.get("REMINDER_TIMES", "09:00,12:00,16:00")
    reminder_times = sorted(
        time.fromisoformat(t.strip()).replace(tzinfo=tz) for t in raw_times.split(",") if t.strip()
    )
    secret = _required("SESSION_SECRET")
    if secret == "change_moi" or len(secret) < 32:
        raise RuntimeError("SESSION_SECRET doit etre une valeur aleatoire d'au moins 32 caracteres")
    return Config(
        discord_token=_required("DISCORD_TOKEN"),
        client_id=_required("DISCORD_CLIENT_ID"),
        client_secret=_required("DISCORD_CLIENT_SECRET"),
        guild_id=int(_required("GUILD_ID")),
        channel_id=int(_required("CHANNEL_ID")),
        allowed_role_id=int(_required("ALLOWED_ROLE_ID")),
        base_url=_required("BASE_URL").rstrip("/"),
        session_secret=secret.encode(),
        web_host=os.environ.get("WEB_HOST", "0.0.0.0"),
        web_port=int(os.environ.get("WEB_PORT", "8080")),
        tz=tz,
        reminder_times=reminder_times,
        db_path=os.environ.get("DB_PATH", "data/frigo.db"),
    )
