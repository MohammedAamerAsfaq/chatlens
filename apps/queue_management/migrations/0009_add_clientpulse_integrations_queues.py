from django.db import migrations


def add_queues(apps, schema_editor):
    Queue = apps.get_model('queue_management', 'QueueDefinition')
    for name, label in (('clientpulse', 'ClientPulse'), ('integrations', 'Integrations')):
        Queue.objects.get_or_create(name=name, defaults={
            'display_name': label, 'max_concurrency': 2,
            'task_timeout_seconds': 120, 'lock_timeout_seconds': 180,
            'default_max_attempts': 3,
        })


def remove_queues(apps, schema_editor):
    apps.get_model('queue_management', 'QueueDefinition').objects.filter(
        name__in=('clientpulse', 'integrations'),
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0008_add_outbound_queue')]
    operations = [migrations.RunPython(add_queues, remove_queues)]
