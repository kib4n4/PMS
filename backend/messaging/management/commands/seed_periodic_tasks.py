# backend/messaging/management/commands/seed_periodic_tasks.py

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask

# None of these five tasks are scheduled anywhere until this command runs
# once per environment — django_celery_beat's DatabaseScheduler (see
# config/settings.py:CELERY_BEAT_SCHEDULER) reads PeriodicTask rows from
# the DB, and nothing in the repo seeded any until now. Lookup key is
# `name` (PeriodicTask's actual unique field), so re-running this is safe.
PERIODIC_TASKS = [
    {
        "name": "Generate monthly fee invoices",
        "task": "billing.tasks.generate_fee_invoices",
        "crontab": {"minute": "0", "hour": "2", "day_of_month": "1", "month_of_year": "*", "day_of_week": "*"},
    },
    {
        "name": "Reconcile landlord transactions (nightly)",
        "task": "billing.tasks.reconcile_all_landlords",
        "crontab": {"minute": "0", "hour": "3", "day_of_month": "*", "month_of_year": "*", "day_of_week": "*"},
    },
    {
        "name": "Sweep reseller payouts",
        "task": "partners.tasks.sweep_reseller_payouts",
        "crontab": {"minute": "0", "hour": "4", "day_of_month": "1", "month_of_year": "*", "day_of_week": "*"},
    },
    {
        "name": "Sweep investor payouts",
        "task": "partners.tasks.sweep_investor_payouts",
        "crontab": {"minute": "30", "hour": "4", "day_of_month": "1", "month_of_year": "*", "day_of_week": "*"},
    },
    {
        "name": "Send rent reminders",
        "task": "messaging.tasks.send_rent_reminders",
        "crontab": {"minute": "0", "hour": "8", "day_of_month": "*", "month_of_year": "*", "day_of_week": "*"},
    },
]


class Command(BaseCommand):
    help = (
        "Idempotently seeds django-celery-beat PeriodicTask rows for the platform's scheduled tasks "
        "(fee invoicing, reconciliation, payout sweeps, rent reminders). Run once per environment "
        "after migrate — scheduling is an operational decision, not something migrations should do."
    )

    def handle(self, *args, **options):
        created_count = 0
        for entry in PERIODIC_TASKS:
            schedule, _ = CrontabSchedule.objects.get_or_create(**entry["crontab"])
            _, created = PeriodicTask.objects.get_or_create(
                name=entry["name"],
                defaults={"task": entry["task"], "crontab": schedule, "enabled": True},
            )
            if created:
                created_count += 1
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {created_count} new periodic task(s) ({len(PERIODIC_TASKS)} total checked).")
        )
