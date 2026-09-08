from django.core.management.base import BaseCommand

from apps.queue_management.operations_ui import run_task_operations_ui


class Command(BaseCommand):
    help = 'Open the local desktop Task Operations Monitor outside IIS.'

    def add_arguments(self, parser):
        parser.add_argument('--refresh-seconds', type=int, default=3)

    def handle(self, *args, **options):
        run_task_operations_ui(refresh_seconds=max(1, options['refresh_seconds']))
