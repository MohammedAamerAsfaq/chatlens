import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('tenancy', '0010_harden_company_contacts'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserCompanyPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ui_theme', models.CharField(
                    choices=[('chatlens', 'ChatLens'), ('inspinia', 'Inspinia')],
                    default='chatlens', max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='user_preferences', to='tenancy.company',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='company_preferences', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'tenant_user_company_preference',
                'constraints': [models.UniqueConstraint(
                    fields=('company', 'user'), name='unique_user_company_preference',
                )],
            },
        ),
    ]
