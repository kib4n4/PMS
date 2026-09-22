# backend/credentials/services.py

"""
Read path for DB-driven platform credentials. Every integration client
(Daraja, WhatsApp, Resend, KRA, ...) resolves its platform-level secrets
through get_platform_credential instead of os.environ, so rotating a key
is an admin-panel edit, not a redeploy.
"""

from typing import Optional

from django.core.cache import cache

from .models import PlatformCredential

_CACHE_PREFIX = "platform_credential:"
_CACHE_TTL = 300  # 5 minutes — acceptable staleness window after a rotation


def get_platform_credential(key: str, default: Optional[str] = None) -> Optional[str]:
    cache_key = _CACHE_PREFIX + key
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or default

    try:
        value = PlatformCredential.objects.get(key=key).value
    except PlatformCredential.DoesNotExist:
        return default

    cache.set(cache_key, value or "", _CACHE_TTL)
    return value or default


def invalidate_platform_credential_cache(key: str) -> None:
    cache.delete(_CACHE_PREFIX + key)
