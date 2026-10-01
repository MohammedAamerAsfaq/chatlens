import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('tenancy', '0010_harden_company_contacts'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactMergeCandidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('match_reasons', models.JSONField(blank=True, default=list)),
                ('confidence', models.DecimalField(decimal_places=4, default=1, max_digits=5)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending review'), ('merged', 'Merged'),
                             ('rejected', 'Not a duplicate')],
                    default='pending', max_length=20,
                )),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='contact_merge_candidates', to='tenancy.company',
                )),
                ('left_contact', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='merge_candidates_left', to='tenancy.companycontact',
                )),
                ('right_contact', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='merge_candidates_right', to='tenancy.companycontact',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='contact_merge_candidates_reviewed', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'clientpulse_contact_merge_candidate',
                'ordering': ['-created_at'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('company', 'left_contact', 'right_contact'),
                        name='unique_contact_merge_candidate_pair',
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(left_contact=models.F('right_contact')),
                        name='contact_merge_candidate_distinct_contacts',
                    ),
                ],
            },
        ),
    ]
