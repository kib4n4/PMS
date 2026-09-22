# backend/api_auth/management/commands/create_api_client.py

from django.core.management.base import BaseCommand, CommandError

from api_auth.models import PlatformApiClient
from landlords.models import Landlord


class Command(BaseCommand):
    help = "Create a new external API client (customer key + customer secret). The secret is shown ONCE — store it now."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Human-readable integrator name.")
        parser.add_argument(
            "--landlord-id", required=False,
            help="Scope this client to one landlord's data. Omit for a platform-wide client.",
        )
        parser.add_argument(
            "--scopes", required=False, default="invoices:read",
            help="Comma-separated scopes, e.g. 'invoices:read,payments:read'.",
        )

    def handle(self, *args, **options):
        landlord = None
        if options["landlord_id"]:
            try:
                landlord = Landlord.objects.get(id=options["landlord_id"])
            except Landlord.DoesNotExist as exc:
                raise CommandError(f"No landlord with id {options['landlord_id']}") from exc

        scopes = [s.strip() for s in options["scopes"].split(",") if s.strip()]
        client, secret = PlatformApiClient.generate(name=options["name"], scopes=scopes, landlord=landlord)

        self.stdout.write(self.style.SUCCESS(f"Created API client '{client.name}'"))
        self.stdout.write(f"client_id:     {client.client_id}")
        self.stdout.write(f"client_secret: {secret}")
        self.stdout.write(self.style.WARNING("Store the client_secret now — it cannot be shown again."))
