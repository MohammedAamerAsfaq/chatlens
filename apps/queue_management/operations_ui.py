"""Local desktop monitor for operators running queue processes interactively.

This is intentionally separate from the IIS-hosted Vue screen. It reads the
durable queue tables directly, so it remains useful when IIS is restarting.
"""
import socket
import subprocess
import sys

from django.db.models import Count, Min
from django.utils import timezone

from apps.task_management.models import BackgroundTask, BackgroundTaskSchedule
from .models import BackgroundWorker, QueueDefinition

UI_PORT = 51379


def launch_task_operations_ui():
    """Start one desktop monitor per logged-in desktop, not one per worker."""
    try:
        with socket.create_connection(('127.0.0.1', UI_PORT), timeout=0.2):
            return False
    except OSError:
        pass

    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(
        [sys.executable, 'manage.py', 'run_task_operations_ui'],
        cwd='.',
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return True


def run_task_operations_ui(refresh_seconds=3):
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as exc:
        raise RuntimeError('Tkinter is required for the local Task Operations Monitor.') from exc

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', UI_PORT))
        listener.listen(1)
    except OSError:
        listener.close()
        return

    root = tk.Tk()
    root.title('ChatLens Task Operations Monitor')
    root.geometry('1220x760')
    root.minsize(980, 620)

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('Treeview', rowheight=26, font=('Segoe UI', 9))
    style.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'))

    header = ttk.Frame(root, padding=(18, 15, 18, 8))
    header.pack(fill='x')
    ttk.Label(header, text='Task Operations Monitor', font=('Georgia', 20, 'bold')).pack(side='left')
    status_label = ttk.Label(header, text='Connecting...', foreground='#527062')
    status_label.pack(side='left', padx=18)

    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=18, pady=(0, 18))

    queues_frame = ttk.Frame(notebook, padding=10)
    workers_frame = ttk.Frame(notebook, padding=10)
    tasks_frame = ttk.Frame(notebook, padding=10)
    schedules_frame = ttk.Frame(notebook, padding=10)
    notebook.add(queues_frame, text='Queues')
    notebook.add(workers_frame, text='Workers')
    notebook.add(tasks_frame, text='Tasks')
    notebook.add(schedules_frame, text='Scheduler')

    def tree(parent, columns, widths):
        widget = ttk.Treeview(parent, columns=columns, show='headings')
        for column, width in zip(columns, widths):
            widget.heading(column, text=column.replace('_', ' ').title())
            widget.column(column, width=width, anchor='w')
        scroll = ttk.Scrollbar(parent, orient='vertical', command=widget.yview)
        widget.configure(yscrollcommand=scroll.set)
        widget.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        return widget

    queues_tree = tree(queues_frame, ('queue', 'state', 'pending', 'claimed', 'running', 'retrying', 'failed', 'oldest_pending'), (170, 100, 85, 85, 85, 85, 85, 150))
    workers_tree = tree(workers_frame, ('worker_id', 'state', 'hostname', 'pid', 'queues', 'last_heartbeat'), (310, 100, 180, 75, 230, 220))
    tasks_tree = tree(tasks_frame, ('id', 'task_key', 'queue', 'state', 'attempts', 'worker', 'created', 'feedback'), (65, 270, 110, 100, 85, 170, 170, 340))
    schedules_tree = tree(schedules_frame, ('name', 'task_key', 'queue', 'active', 'next_run', 'last_enqueued', 'last_error'), (220, 260, 100, 75, 180, 180, 290))

    detail = tk.Text(tasks_frame, height=9, wrap='word', font=('Consolas', 9), state='disabled')
    detail.pack(side='bottom', fill='x', pady=(10, 0))
    task_rows = {}

    def stamp(value):
        if not value:
            return '-'
        return timezone.localtime(value).strftime('%Y-%m-%d %H:%M:%S')

    def replace_rows(widget, rows):
        widget.delete(*widget.get_children())
        for row in rows:
            widget.insert('', 'end', values=row)

    def show_task_detail(_event=None):
        selected = tasks_tree.selection()
        if not selected:
            return
        task = task_rows.get(selected[0])
        if not task:
            return
        lines = [
            f"Task #{task.pk} | {task.task_key} | {task.status}",
            f"Correlation: {task.correlation_id or '-'}",
            f"Idempotency: {task.idempotency_key or '-'}",
            f"Payload: {task.payload}",
            f"Result: {task.result}",
            f"Error: {task.last_error or '-'}",
            '', 'Task Event Log:',
        ]
        for event in task.events.order_by('created_at'):
            lines.append(f"{stamp(event.created_at)} | {event.event_type} | attempt {event.attempt_number} | {event.message or event.error}")
        if task.last_traceback:
            lines.extend(['', 'Latest traceback:', task.last_traceback])
        detail.configure(state='normal')
        detail.delete('1.0', 'end')
        detail.insert('1.0', '\n'.join(lines))
        detail.configure(state='disabled')

    tasks_tree.bind('<<TreeviewSelect>>', show_task_detail)

    def refresh():
        try:
            now = timezone.now()
            queue_rows = []
            for queue in QueueDefinition.objects.all():
                counts = {
                    row['status']: row['count']
                    for row in BackgroundTask.objects.filter(queue_name=queue.name).values('status').annotate(count=Count('id'))
                }
                oldest = BackgroundTask.objects.filter(queue_name=queue.name, status=BackgroundTask.STATUS_PENDING).aggregate(value=Min('created_at'))['value']
                state = 'disabled' if not queue.is_enabled else 'paused' if queue.is_paused else 'ready'
                queue_rows.append((queue.name, state, counts.get('pending', 0), counts.get('claimed', 0), counts.get('running', 0), counts.get('retrying', 0), counts.get('failed', 0), f'{int((now - oldest).total_seconds())}s' if oldest else '-'))
            replace_rows(queues_tree, queue_rows)

            replace_rows(workers_tree, [
                (worker.worker_id, worker.status, worker.hostname, worker.process_id, ', '.join(worker.queue_names), stamp(worker.last_heartbeat_at))
                for worker in BackgroundWorker.objects.all()
            ])

            task_rows.clear()
            tasks_tree.delete(*tasks_tree.get_children())
            for task in BackgroundTask.objects.prefetch_related('events').order_by('-created_at')[:200]:
                feedback = task.last_error or ('Completed successfully.' if task.status == 'succeeded' else 'Waiting for worker.')
                item = tasks_tree.insert('', 'end', values=(task.pk, task.task_key, task.queue_name, task.status, f'{task.attempts}/{task.max_attempts}', task.locked_by or '-', stamp(task.created_at), feedback))
                task_rows[item] = task

            replace_rows(schedules_tree, [
                (schedule.name, schedule.task_key, schedule.queue_name, 'yes' if schedule.is_active else 'no', stamp(schedule.next_run_at), stamp(schedule.last_enqueued_at), schedule.last_error or '-')
                for schedule in BackgroundTaskSchedule.objects.all()
            ])
            status_label.configure(text=f'Updated {timezone.localtime(now).strftime("%H:%M:%S")} | {BackgroundTask.objects.filter(status__in=BackgroundTask.ACTIVE_STATUSES).count()} active task(s)', foreground='#237047')
        except Exception as exc:
            status_label.configure(text=f'Unable to refresh: {exc}', foreground='#a62e28')
        root.after(max(1, int(refresh_seconds)) * 1000, refresh)

    def close():
        listener.close()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', close)
    refresh()
    root.mainloop()
