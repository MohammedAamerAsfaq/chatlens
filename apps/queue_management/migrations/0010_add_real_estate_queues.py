from django.db import migrations


QUEUES = (
    ('real_estate_gate', 'Real Estate GatePass', 10),
    ('real_estate_extract', 'Real Estate Extraction', 5),
    ('real_estate_match', 'Real Estate Matching', 5),
    ('real_estate_maintenance', 'Real Estate Maintenance', 2),
)


def add_queues(apps, schema_editor):
    queue_definition = apps.get_model('queue_management', 'QueueDefinition')
    for name, display_name, concurrency in QUEUES:
        queue_definition.objects.get_or_create(
            name=name,
            defaults={
                'display_name': display_name,
                'max_concurrency': concurrency,
                'task_timeout_seconds': 300,
                'lock_timeout_seconds': 300,
                'default_max_attempts': 3,
            },
        )


def remove_queues(apps, schema_editor):
    queue_definition = apps.get_model('queue_management', 'QueueDefinition')
    queue_definition.objects.filter(name__in=[row[0] for row in QUEUES]).delete()


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0009_add_clientpulse_integrations_queues')]
    operations = [migrations.RunPython(add_queues, remove_queues)]
