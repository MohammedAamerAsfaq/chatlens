from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('message_intelligence', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS message_embedding_vector_idx
                ON message_embedding
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """,
            reverse_sql='DROP INDEX IF EXISTS message_embedding_vector_idx;',
        ),
    ]
