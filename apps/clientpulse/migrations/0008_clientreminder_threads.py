import uuid

from django.db import migrations, models
import django.db.models.deletion


def backfill_thread_keys(apps, schema_editor):
    reminder_model = apps.get_model('clientpulse', 'ClientReminder')
    for reminder_id in reminder_model.objects.values_list('pk', flat=True).iterator():
        reminder_model.objects.filter(pk=reminder_id).update(thread_key=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [('clientpulse', '0007_clientpulse_reminder_notification_settings')]

    operations = [
        migrations.AddField(
            model_name='clientreminder',
            name='linked_from',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='linked_follow_ups', to='clientpulse.clientreminder',
            ),
        ),
        migrations.AddField(
            model_name='clientreminder',
            name='thread_key',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_thread_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='clientreminder',
            name='thread_key',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False),
        ),
    ]
