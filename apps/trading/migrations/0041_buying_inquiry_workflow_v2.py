from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenancy', '0002_seed_initial_tenancy_data'),
        ('whatsapp_bridge', '0027_whatsappaccount_last_worker_heartbeat_at'),
        ('trading', '0040_selling_offer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='buyinginquiry',
            name='account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='buying_inquiries', to='whatsapp_bridge.whatsappaccount'),
        ),
        migrations.AlterField(
            model_name='buyinginquiry',
            name='product_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='buyinginquiry',
            name='status',
            field=models.CharField(choices=[('open', 'Open'), ('closed', 'Closed')], db_index=True, default='open', max_length=20),
        ),
        migrations.AlterModelOptions(
            name='buyinginquiry',
            options={'ordering': ['-created_at', '-id'], 'verbose_name_plural': 'buying inquiries'},
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='buying_inquiries', to='tenancy.company'),
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='buying_inquiries_created', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='footer_template',
            field=models.TextField(default='Please reply with availability and best price.'),
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='header_template',
            field=models.TextField(default='Hello, looking to buy:'),
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='product_line_template',
            field=models.TextField(default='- {product_name} - Qty {qty} - Target {price}'),
        ),
        migrations.AddIndex(
            model_name='buyinginquiry',
            index=models.Index(fields=['company', 'status', 'created_at'], name='buyinq_company_status_idx'),
        ),
        migrations.CreateModel(
            name='BuyingInquiryProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(blank=True, null=True)),
                ('target_price', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('currency', models.CharField(blank=True, max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('inquiry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='trading.buyinginquiry')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='buying_inquiry_rows', to='trading.product')),
            ],
            options={
                'db_table': 'trading_buying_inquiry_product',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='BuyingInquirySupplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('auto', 'Auto'), ('manual', 'Manual')], default='manual', max_length=20)),
                ('sent_count', models.PositiveIntegerField(default=0)),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='buying_inquiry_rows', to='whatsapp_bridge.whatsappcontact')),
                ('inquiry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suppliers', to='trading.buyinginquiry')),
                ('source_inquiry_product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='trading.inquiryproduct')),
                ('source_product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='trading.product')),
            ],
            options={
                'db_table': 'trading_buying_inquiry_supplier',
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='buyinginquiryproduct',
            constraint=models.UniqueConstraint(fields=('inquiry', 'product'), name='unique_buying_inquiry_product'),
        ),
        migrations.AddConstraint(
            model_name='buyinginquirysupplier',
            constraint=models.UniqueConstraint(fields=('inquiry', 'contact'), name='unique_buying_inquiry_supplier'),
        ),
    ]
