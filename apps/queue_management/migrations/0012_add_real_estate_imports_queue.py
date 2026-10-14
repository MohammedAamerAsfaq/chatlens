from django.db import migrations


QUEUE_NAME = 'real_estate_imports'


def add_queue(apps, schema_editor):
    apps.get_model('queue_management', 'QueueDefinition').objects.get_or_create(
        name=QUEUE_NAME,
        defaults={
            'display_name': 'Real Estate Imports',
            'max_concurrency': 1,
            'task_timeout_seconds': 300,
            'lock_timeout_seconds': 300,
            'default_max_attempts': 3,
        },
    )


def remove_queue(apps, schema_editor):
    apps.get_model('queue_management', 'QueueDefinition').objects.filter(name=QUEUE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0011_add_real_estate_embeddings_queue')]
    operations = [migrations.RunPython(add_queue, remove_queue)]
