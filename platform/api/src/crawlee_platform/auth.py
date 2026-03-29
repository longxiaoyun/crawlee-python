"""API authentication."""

from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from crawlee_platform.config import Settings
from crawlee_platform.deps import get_settings

_api_key_header = APIKeyHeader(name='X-API-Key', auto_error=False)


async def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    api_key: Annotated[str | None, Security(_api_key_header)],
) -> None:
    """Reject mutating requests when API key is missing or wrong."""
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail='Invalid or missing API key')

