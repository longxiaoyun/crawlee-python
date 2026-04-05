"""Pluggable LLM chat for task assistance."""

from __future__ import annotations

import uuid

import httpx

from crawlee_platform.config import Settings


async def complete_chat(*, settings: Settings, user_message: str) -> tuple[str, str, str | None]:
    """Return (assistant_text, correlation_id, model_id)."""
    correlation_id = str(uuid.uuid4())
    if not settings.openai_api_key:
        reply = (
            'AI is not configured (set PLATFORM_OPENAI_API_KEY). '
            f'Echo: {user_message[:2000]}'
        )
        return reply, correlation_id, None

    url = f'{settings.openai_base_url.rstrip("/")}/chat/completions'
    headers = {'Authorization': f'Bearer {settings.openai_api_key}'}
    body = {
        'model': settings.openai_model,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You help write Crawlee for Python crawlers. '
                    'Import crawlers from crawlee.crawlers (e.g. '
                    'from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext), '
                    'not from a non-existent crawlee.playwright_crawler module. '
                    'Respond concisely; when proposing code, wrap it in a fenced ```python block.'
                ),
            },
            {'role': 'user', 'content': user_message},
        ],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    choice = data['choices'][0]['message']['content']
    model_id = data.get('model', settings.openai_model)
    return choice, correlation_id, model_id
