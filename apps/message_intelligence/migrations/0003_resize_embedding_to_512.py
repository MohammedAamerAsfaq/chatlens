import pgvector.django.vector
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('message_intelligence', '0002_embedding_vector_index'),
    ]

    operations = [
        # Drop the IVFFlat index before altering the column (ALTER TYPE requires it)
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS message_embedding_vector_idx;',
            reverse_sql="""
                CREATE INDEX IF NOT EXISTS message_embedding_vector_idx
                ON message_embedding
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """,
        ),
        # Resize the vector column from 1536 → 512
        migrations.AlterField(
            model_name='messageembedding',
            name='embedding',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=512, null=True),
        ),
        # Recreate the IVFFlat index for 512-dim cosine search
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
