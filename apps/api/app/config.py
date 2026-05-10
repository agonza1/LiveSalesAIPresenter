from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / '.env')


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv('APP_ENV', 'development')
    api_base_url: str = os.getenv('API_BASE_URL', 'http://localhost:8000')
    openai_api_key: str | None = os.getenv('OPENAI_API_KEY')
    openai_realtime_model: str = os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-mini')
    openai_responses_model: str = os.getenv('OPENAI_RESPONSES_MODEL', 'gpt-4.1-mini')
    pipecat_service_url: str = os.getenv('PIPECAT_SERVICE_URL', 'http://localhost:8110')
    heygen_api_key: str | None = os.getenv('HEYGEN_API_KEY')
    heygen_avatar_id: str = os.getenv('HEYGEN_AVATAR_ID', 'default')
    heygen_voice_id: str | None = os.getenv('HEYGEN_VOICE_ID')


settings = Settings()
