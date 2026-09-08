from django.db import migrations


INITIAL_QUEUES = (
    ('default', 'Default'),
    ('automation', 'Automation'),
    ('ai', 'AI'),
    ('embeddings', 'Embeddings'),
    ('recovery', 'Recovery'),
    ('metadata', 'Metadata'),
    ('reports', 'Reports'),
)


def seed_queues(apps, schema_editor):
    QueueDefinition = apps.get_model('queue_management', 'QueueDefinition')
    for name, display_name in INITIAL_QUEUES:
        QueueDefinition.objects.get_or_create(name=name, defaults={'display_name': display_name})


def remove_seeded_queues(apps, schema_editor):
    QueueDefinition = apps.get_model('queue_management', 'QueueDefinition')
    QueueDefinition.objects.filter(name__in=[name for name, _ in INITIAL_QUEUES]).delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0001_initial')]
    operations = [migrations.RunPython(seed_queues, remove_seeded_queues)]
