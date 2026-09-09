import signal
import time

from django.core.management.base import BaseCommand

from apps.queue_management.services import enqueue_due_schedules


class Command(BaseCommand):
    help = 'Enqueue due durable task schedules. This command never executes task handlers.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=float, default=None)
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--no-ui', action='store_true', help='Do not launch the local desktop Task Operations Monitor.')

    def handle(self, *args, **options):
        stopping = False

        def stop(*_args):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        if not options['no_ui'] and not options['once']:
            from apps.queue_management.operations_ui import launch_task_operations_ui
            launch_task_operations_ui()
        while not stopping:
            result = enqueue_due_schedules()
            if result['enqueued'] or result['skipped']:
                self.stdout.write(str(result))
            if options['once']:
                break
            from apps.queue_management.runtime_settings import get_task_runtime_settings
            interval = options['interval'] or get_task_runtime_settings().scheduler_interval_seconds
            time.sleep(max(0.1, interval))
