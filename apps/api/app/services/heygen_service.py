from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class HeyGenService:
    @property
    def enabled(self) -> bool:
        return bool(settings.heygen_api_key)

    def create_streaming_token(self) -> dict[str, Any]:
        if not settings.heygen_api_key:
            raise RuntimeError('HEYGEN_API_KEY is missing')

        response = httpx.post(
            'https://api.heygen.com/v1/streaming.create_token',
            headers={'x-api-key': settings.heygen_api_key},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get('data', {}).get('token') or payload.get('token')
        if not token:
            raise RuntimeError('HeyGen token response did not include a token')
        return {
            'provider': 'heygen',
            'enabled': True,
            'token': token,
            'avatar_id': settings.heygen_avatar_id,
            'voice_id': settings.heygen_voice_id,
        }


heygen_service = HeyGenService()
