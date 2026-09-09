from django.db import migrations


def set_automation_concurrency(apps, schema_editor):
    QueueDefinition = apps.get_model('queue_management', 'QueueDefinition')
    QueueDefinition.objects.filter(name='automation', max_concurrency=1).update(max_concurrency=10)


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0002_seed_initial_queues')]

    operations = [migrations.RunPython(set_automation_concurrency, migrations.RunPython.noop)]
