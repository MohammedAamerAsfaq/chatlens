import signal
import time

from django.core.management.base import BaseCommand

from apps.queue_management.models import QueueDefinition
from apps.queue_management.services import TaskWorker


class Command(BaseCommand):
    help = 'Run durable BackgroundTask workers outside the Django web process.'

    def add_arguments(self, parser):
        parser.add_argument('--queue', action='append', dest='queues')
        parser.add_argument('--limit', type=int, default=1)
        parser.add_argument('--interval', type=float, default=None)
        parser.add_argument('--worker-id', default=None)
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--no-ui', action='store_true', help='Do not launch the local desktop Task Operations Monitor.')

    def handle(self, *args, **options):
        queues = options['queues'] or list(QueueDefinition.objects.filter(is_enabled=True).values_list('name', flat=True))
        if not queues:
            self.stderr.write('No enabled queues available.')
            return
        worker = TaskWorker(queues, worker_id=options['worker_id'])
        if not options['no_ui'] and not options['once']:
            from apps.queue_management.operations_ui import launch_task_operations_ui
            launch_task_operations_ui()
        stopping = False

        def stop(*_args):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        worker.start()
        self.stdout.write(f'Task Worker {worker.worker_id} serving {", ".join(queues)}')
        try:
            while not stopping:
                processed = worker.run_once(limit=options['limit'])
                if options['once']:
                    break
                if not processed:
                    interval = options['interval']
                    if interval is None:
                        interval = min(QueueDefinition.objects.filter(name__in=queues).values_list('poll_interval_seconds', flat=True), default=2)
                    time.sleep(max(0.1, interval))
        finally:
            worker.stop()
