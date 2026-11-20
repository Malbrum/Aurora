"""Innstillinger fra .env.agentic. Egen fil, så den gamle appens Settings (extra=forbid) ikke påvirkes."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    model: str
    inference_geo: str | None
    max_turns: int
    brp_base_url: str
    brp_username: str
    brp_password: str
    gmail_account: str
    gmail_channel: str
    gmail_client_id: str
    gmail_client_secret: str
    gmail_refresh_token: str
    gmail_days: int
    db_path: Path


def load(path: Path | None = None) -> Config:
    values = {**dotenv_values(path or ROOT / '.env.agentic'), **os.environ}
    get = lambda key, default='': (values.get(key) or default)
    return Config(
        anthropic_api_key=get('ANTHROPIC_API_KEY'),
        model=get('ANTHROPIC_MODEL', 'claude-opus-5-5'),
        inference_geo=get('ANTHROPIC_INFERENCE_GEO') or None,
        max_turns=int(get('MAX_TURNS', '12')),
        brp_base_url=get('BRP_API_BASE_URL', 'https://roabadet.brpsystems.com/apiserver'),
        brp_username=get('BRP_API_USERNAME'),
        brp_password=get('BRP_API_PASSWORD'),
        gmail_account=get('GMAIL_ACCOUNT'),
        gmail_channel=get('GMAIL_CHANNEL_ADDRESS', 'post@roabadet.no'),
        gmail_client_id=get('GMAIL_OAUTH_CLIENT_ID'),
        gmail_client_secret=get('GMAIL_OAUTH_CLIENT_SECRET'),
        gmail_refresh_token=get('GMAIL_OAUTH_REFRESH_TOKEN'),
        gmail_days=int(get('GMAIL_DAYS', '14')),
        db_path=ROOT / get('AGENTIC_DB', 'data/agentic.db'),
    )
