import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0052_automation_regenerate_price_list'),
        ('whatsapp_bridge', '0031_outbound_execution'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyinginquiry',
            name='audience_type',
            field=models.CharField(
                choices=[('contacts', 'Contacts'), ('groups', 'Groups')],
                db_index=True,
                default='contacts',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sellingoffer',
            name='audience_type',
            field=models.CharField(
                choices=[('contacts', 'Contacts'), ('groups', 'Groups')],
                db_index=True,
                default='contacts',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='BuyingInquiryGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sent_count', models.PositiveIntegerField(default=0)),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='buying_inquiry_rows', to='whatsapp_bridge.whatsappgroup')),
                ('inquiry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='trading.buyinginquiry')),
            ],
            options={'db_table': 'trading_buying_inquiry_group', 'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='SellingOfferGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sent_count', models.PositiveIntegerField(default=0)),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='selling_offer_rows', to='whatsapp_bridge.whatsappgroup')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='trading.sellingoffer')),
            ],
            options={'db_table': 'trading_selling_offer_group', 'ordering': ['id']},
        ),
        migrations.AddConstraint(
            model_name='buyinginquirygroup',
            constraint=models.UniqueConstraint(fields=('inquiry', 'group'), name='unique_buying_inquiry_group'),
        ),
        migrations.AddConstraint(
            model_name='sellingoffergroup',
            constraint=models.UniqueConstraint(fields=('offer', 'group'), name='unique_selling_offer_group'),
        ),
    ]
