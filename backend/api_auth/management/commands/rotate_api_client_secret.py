# backend/api_auth/management/commands/rotate_api_client_secret.py

from django.core.management.base import BaseCommand, CommandError

from api_auth.models import PlatformApiClient


class Command(BaseCommand):
    help = (
        "Rotate the client_secret for an existing external API client (e.g. after a suspected leak). "
        "The client_id, scopes, and landlord binding are unchanged. The new secret is shown ONCE."
    )

    def add_arguments(self, parser):
        parser.add_argument("--client-id", required=True, help="The client_id to rotate, e.g. pms_1a2b3c4d5e6f7g8h.")

    def handle(self, *args, **options):
        try:
            client = PlatformApiClient.objects.get(client_id=options["client_id"])
        except PlatformApiClient.DoesNotExist as exc:
            raise CommandError(f"No API client with client_id {options['client_id']}") from exc

        new_secret = client.rotate_secret()

        self.stdout.write(self.style.SUCCESS(f"Rotated secret for '{client.name}' ({client.client_id})"))
        self.stdout.write(f"client_secret: {new_secret}")
        self.stdout.write(self.style.WARNING("Store the client_secret now — it cannot be shown again. The old secret no longer works."))
