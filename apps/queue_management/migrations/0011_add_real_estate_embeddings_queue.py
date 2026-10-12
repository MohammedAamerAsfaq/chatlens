from django.db import migrations


QUEUE_NAME = 'real_estate_embeddings'


def add_queue(apps, schema_editor):
    queue_definition = apps.get_model('queue_management', 'QueueDefinition')
    queue_definition.objects.get_or_create(
        name=QUEUE_NAME,
        defaults={
            'display_name': 'Real Estate Embeddings',
            'max_concurrency': 5,
            'task_timeout_seconds': 300,
            'lock_timeout_seconds': 300,
            'default_max_attempts': 3,
        },
    )


def remove_queue(apps, schema_editor):
    apps.get_model('queue_management', 'QueueDefinition').objects.filter(
        name=QUEUE_NAME,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0010_add_real_estate_queues')]
    operations = [migrations.RunPython(add_queue, remove_queue)]
