# backend/credentials/fields.py

"""
Field-level encryption for DB-stored third-party credentials (Daraja,
WhatsApp, Resend, KRA, ...). Values are encrypted with Fernet before they
ever reach Postgres, using a master key from CREDENTIAL_ENCRYPTION_KEY.
This is what makes "database driven" credentials safe to store directly
instead of routing every secret through an external secrets manager.

Note: Fernet ciphertext is non-deterministic (it embeds a timestamp/IV),
so equality lookups against an EncryptedSecretField (`.filter(value=...)`)
will never match. Nothing in this codebase needs to query by secret
value, so that's an accepted trade-off, not an oversight.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

# SECURITY WARNING: dev-only fallback key, same spirit as
# DJANGO_SECRET_KEY's dev fallback in settings.py. Any real deployment
# MUST set CREDENTIAL_ENCRYPTION_KEY (generate one with
# `Fernet.generate_key()`) — every credential encrypted under this
# fallback becomes unrecoverable the moment a real key is set.
_DEV_ONLY_KEY = b"6bY8Vv2m6qk0G9nF3q9Zk1r4wQvB7yq3T2sH0pQeC3Y="

_fernet = None
_warned_dev_key = False


def _get_fernet() -> Fernet:
    global _fernet, _warned_dev_key
    if _fernet is not None:
        return _fernet

    key = getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "") or ""
    if not key:
        if not _warned_dev_key:
            logger.warning(
                "CREDENTIAL_ENCRYPTION_KEY is not set — using a fixed dev-only "
                "fallback key. Do not store real credentials until a real key "
                "is configured; every value encrypted under the fallback is "
                "unrecoverable once a real key is set."
            )
            _warned_dev_key = True
        key = _DEV_ONLY_KEY
    elif isinstance(key, str):
        key = key.encode()

    _fernet = Fernet(key)
    return _fernet


class EncryptedSecretField(models.TextField):
    """
    Transparent on the Python side: read the field and get plaintext,
    assign plaintext and it's encrypted before it touches the DB. Blank
    values pass through as-is so `blank=True` fields don't need
    special-casing.
    """

    description = "An encrypted string (Fernet)"

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            logger.error(
                "Failed to decrypt %s — wrong CREDENTIAL_ENCRYPTION_KEY or corrupted value",
                self.attname,
            )
            raise

    def get_prep_value(self, value):
        if not value:
            return value
        if not isinstance(value, str):
            value = str(value)
        return _get_fernet().encrypt(value.encode()).decode()

    def to_python(self, value):
        return value
