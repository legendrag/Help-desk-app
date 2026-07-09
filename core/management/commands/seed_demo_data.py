from django.core.management.base import BaseCommand

from core.seeds.runner import clear_seed, run_seed


class Command(BaseCommand):
    help = "Seed the full DeskPlus system with demo roles, users, tickets, KB, news, and notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove previously seeded demo data before seeding again.",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Password for demo users (default: demo1234). Admin uses DEFAULT_SUPERADMIN_PASSWORD.",
        )
        parser.add_argument(
            "--skip-tickets",
            action="store_true",
            help="Skip ticket/message seeding.",
        )
        parser.add_argument(
            "--skip-notifications",
            action="store_true",
            help="Skip in-app notification seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing demo seed data...")
            clear_seed(stdout=self.stdout)

        run_seed(
            password=options["password"],
            skip_tickets=options["skip_tickets"],
            skip_notifications=options["skip_notifications"],
            stdout=self.stdout,
            style=self.style,
        )
