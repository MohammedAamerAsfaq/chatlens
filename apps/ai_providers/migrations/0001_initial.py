from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AIProviderConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_name', models.CharField(max_length=100)),
                ('provider', models.CharField(
                    choices=[
                        ('voyage', 'Voyage AI'),
                        ('openai', 'OpenAI'),
                        ('anthropic', 'Anthropic'),
                        ('cohere', 'Cohere'),
                    ],
                    max_length=50,
                )),
                ('capability', models.CharField(
                    choices=[
                        ('embedding', 'Embeddings'),
                        ('chat', 'Chat / Completion'),
                    ],
                    max_length=50,
                )),
                ('api_key', models.TextField()),
                ('model', models.CharField(max_length=100)),
                ('base_url', models.URLField(blank=True, default='')),
                ('extra_config', models.JSONField(blank=True, default=dict)),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['capability', '-is_active', 'display_name'],
            },
        ),
    ]
