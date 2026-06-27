from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_providers', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiproviderconfig',
            name='capability',
            field=models.CharField(
                choices=[
                    ('embedding', 'Embeddings'),
                    ('chat', 'Chat / Completion'),
                    ('agent', 'General AI Agent'),
                ],
                max_length=50,
            ),
        ),
    ]
