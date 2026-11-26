"""python manage.py purge_login_attempts [--days 30]

Retention for failed login attempts (in production: a scheduled job, e.g. daily cron).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from authentication.services import purge_failed_login_attempts


class Command(BaseCommand):
    help = "Delete failed login attempts older than the given number of days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="Retention period (default: 30).")

    def handle(self, *args, days: int, **options):
        if days < 1:
            raise CommandError("--days must be at least 1.")
        deleted = purge_failed_login_attempts(timedelta(days=days))
        self.stdout.write(f"Deleted {deleted} failed login attempt(s) older than {days} day(s).")
