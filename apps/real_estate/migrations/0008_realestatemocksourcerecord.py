from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('real_estate', '0007_prospect_inventory_alignment'),
        ('tenancy', '0013_add_real_estate_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='RealEstateMockSourceRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('import_run_id', models.UUIDField(db_index=True)),
                ('source_file_name', models.CharField(max_length=500)),
                ('source_file_checksum', models.CharField(db_index=True, max_length=64)),
                ('source_sheet_name', models.CharField(max_length=255)),
                ('source_sheet_index', models.PositiveIntegerField()),
                ('source_row_number', models.PositiveIntegerField()),
                ('row_kind', models.CharField(choices=[('header', 'Header'), ('data', 'Data'), ('summary', 'Summary'), ('unknown', 'Unknown')], default='data', max_length=16)),
                ('raw_values', models.JSONField(default=list)),
                ('display_values', models.JSONField(default=list)),
                ('row_checksum', models.CharField(max_length=64)),
                ('processing_status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('processed', 'Processed'), ('failed', 'Failed'), ('skipped', 'Skipped')], db_index=True, default='pending', max_length=16)),
                ('processing_notes', models.TextField(blank=True)),
                ('imported_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='real_estate_mock_source_records', to='tenancy.company')),
            ],
            options={
                'db_table': 'real_estate_mock_source_record',
                'ordering': ['source_file_name', 'source_sheet_index', 'source_row_number'],
            },
        ),
        migrations.AddConstraint(
            model_name='realestatemocksourcerecord',
            constraint=models.UniqueConstraint(fields=('company', 'source_file_name', 'source_file_checksum', 'source_sheet_index', 'source_row_number'), name='re_mock_source_identity_uniq'),
        ),
        migrations.AddIndex(
            model_name='realestatemocksourcerecord',
            index=models.Index(fields=['company', 'processing_status'], name='re_mock_company_status_idx'),
        ),
        migrations.AddIndex(
            model_name='realestatemocksourcerecord',
            index=models.Index(fields=['company', 'source_file_name'], name='re_mock_company_file_idx'),
        ),
    ]
