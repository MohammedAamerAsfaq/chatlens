from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_providers', '0007_add_glm_provider'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiproviderconfig',
            name='provider',
            field=models.CharField(
                choices=[
                    ('voyage', 'Voyage AI'),
                    ('openai', 'OpenAI'),
                    ('anthropic', 'Anthropic'),
                    ('google', 'Google Gemini'),
                    ('deepseek', 'DeepSeek'),
                    ('qwen', 'Qwen (Alibaba)'),
                    ('kimi', 'Kimi (Moonshot)'),
                    ('glm', 'GLM (Zhipu AI)'),
                    ('openrouter', 'OpenRouter'),
                    ('groq', 'Groq'),
                    ('mistral', 'Mistral AI'),
                    ('grok', 'Grok (xAI)'),
                    ('perplexity', 'Perplexity'),
                    ('together', 'Together AI'),
                    ('cohere', 'Cohere'),
                    ('jina', 'Jina AI'),
                    ('lm_studio', 'LM Studio Local'),
                    ('other', 'Other'),
                ],
                max_length=50,
            ),
        ),
    ]
