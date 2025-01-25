from django.db import migrations, models
from pgvector.django import VectorExtension

class Migration(migrations.Migration):
    dependencies = [
        ('detective', '0001_initial'),
    ]

    operations = [
        VectorExtension(),
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS vector;'),
        migrations.RunSQL(
            'ALTER TABLE detective_rawstatistics ADD COLUMN evaluation_embedding vector(512);'
        ),
        migrations.RunSQL(
            'CREATE INDEX ON detective_rawstatistics USING ivfflat (evaluation_embedding vector_cosine_ops) WITH (lists = 100);'
        ),
    ]