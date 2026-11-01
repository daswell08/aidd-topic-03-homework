from django.core.management.base import BaseCommand

from config.settings import TINKOFF_TOKEN
from dashboard.models import Share


class Command(BaseCommand):
    help = "Add shares to DB"

    def handle(self, *args, **options):
        if not TINKOFF_TOKEN:
            self.stderr.write("TINKOFF_TOKEN is not configured")
            return

        try:
            from tinkoff.invest import Client
        except ImportError:
            self.stderr.write("Package tinkoff-investments is not installed")
            return

        created_count = 0
        with Client(TINKOFF_TOKEN) as client:
            shares = client.instruments.shares()
            for share in shares.instruments:
                _, created = Share.objects.get_or_create(
                    figi=share.figi,
                    defaults={
                        "name": share.name,
                        "isin": share.isin,
                        "ticker": share.ticker,
                        "currency": share.currency,
                        "uid": share.uid,
                    },
                )
                if created:
                    created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} shares"))
