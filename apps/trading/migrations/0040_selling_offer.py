from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenancy', '0002_seed_initial_tenancy_data'),
        ('whatsapp_bridge', '0027_whatsappaccount_last_worker_heartbeat_at'),
        ('trading', '0039_alter_aiparsinglog_company_disabled'),
    ]

    operations = [
        migrations.CreateModel(
            name='SellingOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('open', 'Open'), ('closed', 'Closed')], db_index=True, default='open', max_length=20)),
                ('header_template', models.TextField(default='Hello, available stock offer:')),
                ('product_line_template', models.TextField(default='- {product_name} - Qty {qty} - {price}')),
                ('footer_template', models.TextField(default='Reply with required quantity. Subject to availability.')),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='selling_offers', to='tenancy.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='selling_offers_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'trading_selling_offer',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['company', 'status', 'created_at'], name='selloffer_company_status_idx')],
            },
        ),
        migrations.CreateModel(
            name='SellingOfferProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(blank=True, null=True)),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('currency', models.CharField(blank=True, max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='trading.sellingoffer')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='selling_offer_rows', to='trading.product')),
            ],
            options={
                'db_table': 'trading_selling_offer_product',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='SellingOfferCustomer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('auto', 'Auto'), ('manual', 'Manual')], default='manual', max_length=20)),
                ('sent_count', models.PositiveIntegerField(default=0)),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='selling_offer_rows', to='whatsapp_bridge.whatsappcontact')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customers', to='trading.sellingoffer')),
                ('source_inquiry_product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='trading.inquiryproduct')),
                ('source_product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='trading.product')),
            ],
            options={
                'db_table': 'trading_selling_offer_customer',
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='sellingofferproduct',
            constraint=models.UniqueConstraint(fields=('offer', 'product'), name='unique_selling_offer_product'),
        ),
        migrations.AddConstraint(
            model_name='sellingoffercustomer',
            constraint=models.UniqueConstraint(fields=('offer', 'contact'), name='unique_selling_offer_customer'),
        ),
    ]
