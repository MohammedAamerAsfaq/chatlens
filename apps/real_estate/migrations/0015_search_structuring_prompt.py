from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('real_estate', '0014_realestateopportunity_source_contact_detail_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realestateagentcalllog',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('gate', 'Real Estate GatePass'),
                    ('extraction', 'Real Estate Extraction'),
                    ('match_rerank', 'Real Estate Match Reranking'),
                    ('search_structuring', 'Opportunity Search Structuring'),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='realestatepromptconfig',
            name='key',
            field=models.CharField(
                choices=[
                    ('gate', 'Real Estate GatePass'),
                    ('extraction', 'Real Estate Classification and Extraction'),
                    ('match_rerank', 'Real Estate Match Reranking'),
                    ('search_structuring', 'Opportunity Search Structuring'),
                ],
                max_length=100,
            ),
        ),
    ]
