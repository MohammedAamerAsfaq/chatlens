from django.db import migrations


QUEUES = (
    ('v2_pass1', 'V2 Classification Pass 1', 10),
    ('v2_pass2', 'V2 Classification Pass 2', 5),
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
    dependencies = [('queue_management', '0006_add_ingestion_queues')]
    operations = [migrations.RunPython(add_queues, remove_queues)]
