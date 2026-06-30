from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0009_add_username_contact'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wa_group_id', models.CharField(max_length=255)),
                ('name', models.CharField(blank=True, max_length=512)),
                ('description', models.TextField(blank=True)),
                ('owner_jid', models.CharField(blank=True, max_length=255)),
                ('is_community', models.BooleanField(default=False)),
                ('participant_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='groups',
                    to='whatsapp_bridge.whatsappaccount',
                )),
                ('chat', models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='group',
                    to='whatsapp_bridge.whatsappchat',
                )),
                ('community', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sub_groups',
                    to='whatsapp_bridge.whatsappgroup',
                )),
            ],
            options={
                'db_table': 'whatsapp_group',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='whatsappgroup',
            constraint=models.UniqueConstraint(
                fields=['account', 'wa_group_id'],
                name='unique_account_wa_group_id',
            ),
        ),
        migrations.CreateModel(
            name='WhatsAppGroupParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wa_jid', models.CharField(max_length=255)),
                ('role', models.CharField(
                    choices=[('member', 'Member'), ('admin', 'Admin'), ('superadmin', 'Superadmin')],
                    default='member',
                    max_length=20,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='participants',
                    to='whatsapp_bridge.whatsappgroup',
                )),
                ('contact', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='group_memberships',
                    to='whatsapp_bridge.whatsappcontact',
                )),
            ],
            options={
                'db_table': 'whatsapp_group_participant',
                'ordering': ['-role', 'wa_jid'],
            },
        ),
        migrations.AddConstraint(
            model_name='whatsappgroupparticipant',
            constraint=models.UniqueConstraint(
                fields=['group', 'wa_jid'],
                name='unique_group_participant',
            ),
        ),
    ]
