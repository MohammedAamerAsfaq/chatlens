from django.db import migrations


QUEUES = (
    ('history_ingestion', 'WhatsApp History Ingestion', 2),
    ('history_embedding_dispatch', 'History Embedding Dispatch', 4),
    ('live_ingestion', 'WhatsApp Live Ingestion', 10),
)


def add_queues(apps, schema_editor):
    QueueDefinition = apps.get_model('queue_management', 'QueueDefinition')
    for name, display_name, concurrency in QUEUES:
        QueueDefinition.objects.get_or_create(
            name=name,
            defaults={
                'display_name': display_name,
                'max_concurrency': concurrency,
                'task_timeout_seconds': 300,
            },
        )


def remove_queues(apps, schema_editor):
    QueueDefinition = apps.get_model('queue_management', 'QueueDefinition')
    QueueDefinition.objects.filter(name__in=[row[0] for row in QUEUES]).delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0005_task_runtime_settings')]
    operations = [migrations.RunPython(add_queues, remove_queues)]
