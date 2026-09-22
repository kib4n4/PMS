# backend/credentials/tests.py

from django.db import connection
from django.test import TestCase

from .models import PlatformCredential, PlatformCredentialKey
from .services import get_platform_credential


class EncryptedSecretFieldTests(TestCase):
    def test_value_is_encrypted_at_rest(self):
        # Deliberately not filtered by id: UUIDField's on-disk
        # representation differs by backend (bare hex on SQLite, native
        # uuid on Postgres), so this stays portable by relying on being
        # the only row in a fresh test database instead.
        PlatformCredential.objects.create(
            key=PlatformCredentialKey.RESEND_API_KEY, value="re_super_secret_value"
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT value FROM credentials_platformcredential")
            raw_value = cursor.fetchone()[0]
        self.assertNotEqual(raw_value, "re_super_secret_value")

    def test_round_trips_through_save_and_reload(self):
        cred = PlatformCredential.objects.create(
            key=PlatformCredentialKey.WHATSAPP_ACCESS_TOKEN, value="token-abc-123"
        )
        reloaded = PlatformCredential.objects.get(pk=cred.pk)
        self.assertEqual(reloaded.value, "token-abc-123")

    def test_blank_value_stored_as_blank(self):
        cred = PlatformCredential.objects.create(
            key=PlatformCredentialKey.WHATSAPP_VERIFY_TOKEN, value=""
        )
        reloaded = PlatformCredential.objects.get(pk=cred.pk)
        self.assertEqual(reloaded.value, "")


class GetPlatformCredentialServiceTests(TestCase):
    def test_returns_default_when_missing(self):
        self.assertEqual(get_platform_credential("does_not_exist", default="fallback"), "fallback")

    def test_returns_stored_value(self):
        PlatformCredential.objects.create(
            key=PlatformCredentialKey.PLATFORM_DARAJA_SHORTCODE, value="174379"
        )
        self.assertEqual(get_platform_credential(PlatformCredentialKey.PLATFORM_DARAJA_SHORTCODE), "174379")

    def test_cache_invalidated_on_save(self):
        cred = PlatformCredential.objects.create(
            key=PlatformCredentialKey.WHATSAPP_APP_SECRET, value="first"
        )
        self.assertEqual(get_platform_credential(PlatformCredentialKey.WHATSAPP_APP_SECRET), "first")
        cred.value = "second"
        cred.save()
        self.assertEqual(get_platform_credential(PlatformCredentialKey.WHATSAPP_APP_SECRET), "second")
