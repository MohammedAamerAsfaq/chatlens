from django.db import migrations


def add_queue(apps, schema_editor):
    QueueDefinition = apps.get_model('queue_management', 'QueueDefinition')
    QueueDefinition.objects.get_or_create(
        name='outbound',
        defaults={
            'display_name': 'WhatsApp Outbound',
            'max_concurrency': 10,
            'task_timeout_seconds': 60,
            'lock_timeout_seconds': 90,
            'default_max_attempts': 3,
        },
    )


def remove_queue(apps, schema_editor):
    apps.get_model('queue_management', 'QueueDefinition').objects.filter(name='outbound').delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0007_add_v2_classification_queues')]
    operations = [migrations.RunPython(add_queue, remove_queue)]
