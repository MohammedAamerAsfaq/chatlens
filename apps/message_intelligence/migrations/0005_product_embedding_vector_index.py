from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('message_intelligence', '0004_productembedding'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS product_embedding_vector_idx
                ON product_embedding
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """,
            reverse_sql='DROP INDEX IF EXISTS product_embedding_vector_idx;',
        ),
    ]
