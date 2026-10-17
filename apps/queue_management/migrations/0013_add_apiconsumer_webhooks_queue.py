from django.db import migrations


def add_queue(apps, schema_editor):
    QueueDefinition = apps.get_model('queue_management', 'QueueDefinition')
    QueueDefinition.objects.get_or_create(
        name='apiconsumer_webhooks',
        defaults={
            'display_name': 'API Consumer Webhooks',
            'max_concurrency': 5,
            'task_timeout_seconds': 15,
            'lock_timeout_seconds': 30,
            'default_max_attempts': 5,
        },
    )


def remove_queue(apps, schema_editor):
    apps.get_model('queue_management', 'QueueDefinition').objects.filter(name='apiconsumer_webhooks').delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0012_add_real_estate_imports_queue')]
    operations = [migrations.RunPython(add_queue, remove_queue)]
