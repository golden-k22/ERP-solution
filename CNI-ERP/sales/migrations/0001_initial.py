# Generated by Django 3.2.16 on 2024-07-15 02:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsignature.fields
import sales.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cities_light', '0011_alter_city_country_alter_city_region_and_more'),
        ('accounts', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=150, null=True, unique=True)),
                ('address', models.CharField(blank=True, max_length=100, null=True)),
                ('unit', models.CharField(blank=True, max_length=100, null=True)),
                ('postal_code', models.IntegerField(default=0)),
                ('associate', models.CharField(choices=[('Customer', 'Customer'), ('Supplier', 'Supplier'), ('Partner', 'Partner')], default='Customer', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('country', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='cities_light.country')),
            ],
            options={
                'db_table': 'tb_company',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contact_person', models.CharField(blank=True, max_length=100, null=True)),
                ('salutation', models.CharField(choices=[('Mr', 'Mr'), ('Mrs', 'Mrs'), ('Ms', 'Ms'), ('Mdm', 'Mdm'), ('Dr', 'Dr')], default='Mr', max_length=100)),
                ('tel', models.CharField(blank=True, max_length=150, null=True)),
                ('did', models.CharField(blank=True, max_length=150, null=True)),
                ('mobile', models.CharField(blank=True, max_length=150, null=True)),
                ('fax', models.CharField(blank=True, max_length=150, null=True)),
                ('email', models.EmailField(blank=True, max_length=250, null=True)),
                ('role', models.CharField(choices=[('Director', 'Director'), ('Manager', 'Manager'), ('Purchaser', 'Purchaser'), ('Contract', 'Contract'), ('Sales', 'Sales'), ('Others', 'Others')], default='Director', max_length=100)),
                ('created_by', models.CharField(blank=True, max_length=150, null=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.company')),
            ],
            options={
                'db_table': 'tb_contact',
            },
        ),
        migrations.CreateModel(
            name='ParentSubject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(blank=True, max_length=256, null=True)),
            ],
            options={
                'db_table': 'tb_parent_subject',
            },
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'db_table': 'tb_payment',
            },
        ),
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, null=True, unique=True)),
            ],
            options={
                'db_table': 'tb_position',
            },
        ),
        migrations.CreateModel(
            name='ProductSales',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prod_sale_id', models.CharField(blank=True, max_length=100, null=True)),
                ('company_name', models.CharField(blank=True, max_length=100, null=True)),
                ('worksite_address', models.CharField(blank=True, max_length=255, null=True)),
                ('email', models.CharField(blank=True, max_length=254, null=True)),
                ('tel', models.CharField(blank=True, max_length=50, null=True)),
                ('fax', models.CharField(blank=True, max_length=50, null=True)),
                ('RE', models.TextField(blank=True, null=True)),
                ('variation_order', models.CharField(blank=True, max_length=100, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('sales_status', models.CharField(choices=[('Open', 'Open'), ('Completed', 'Completed'), ('Closed', 'Closed')], default='Open', max_length=255)),
                ('company_nameid', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.company')),
                ('contact_person', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.contact')),
            ],
            options={
                'db_table': 'tb_product_sales',
            },
        ),
        migrations.CreateModel(
            name='ProductSalesDo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('do_no', models.CharField(blank=True, max_length=100, null=True)),
                ('status', models.CharField(choices=[('Open', 'Open'), ('Signed', 'Signed')], default='Open', max_length=100)),
                ('date', models.DateField(blank=True, null=True)),
                ('ship_to', models.TextField(blank=True, null=True)),
                ('document', models.FileField(blank=True, null=True, upload_to=sales.models.content_file_delivery)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('invoice_no', models.CharField(blank=True, max_length=8, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='productsalesdo_created_by', to=settings.AUTH_USER_MODEL)),
                ('product_sales', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.productsales')),
                ('upload_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='productsalesdo_upload_by', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'tb_product_sales_do',
            },
        ),
        migrations.CreateModel(
            name='Quotation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qtt_id', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('address', models.CharField(blank=True, max_length=100, null=True)),
                ('unit', models.CharField(blank=True, max_length=100, null=True)),
                ('tel', models.CharField(blank=True, max_length=50, null=True)),
                ('fax', models.CharField(blank=True, max_length=50, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('sale_type', models.CharField(choices=[('Project', 'Project'), ('Maintenance', 'Maintenance'), ('Sales', 'Sales')], max_length=100)),
                ('date', models.DateField(blank=True, null=True)),
                ('qtt_status', models.CharField(choices=[('Open', 'Open'), ('Awarded', 'Awarded'), ('Closed', 'Closed'), ('Loss', 'Loss')], default='Open', max_length=100)),
                ('RE', models.TextField(blank=True, null=True)),
                ('total', models.DecimalField(decimal_places=2, max_digits=20, null=True)),
                ('gst', models.DecimalField(decimal_places=2, max_digits=20, null=True)),
                ('finaltotal', models.DecimalField(decimal_places=2, max_digits=8, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('sale_person', models.CharField(blank=True, max_length=100, null=True)),
                ('auth_signature', models.CharField(blank=True, max_length=100, null=True)),
                ('estimated_mandays', models.CharField(blank=True, max_length=100, null=True)),
                ('auth_name', models.CharField(blank=True, max_length=100, null=True)),
                ('signature_date', models.DateField(blank=True, null=True)),
                ('po_no', models.CharField(blank=True, max_length=100, null=True)),
                ('validity', models.CharField(blank=True, max_length=255, null=True)),
                ('terms', models.CharField(blank=True, max_length=255, null=True)),
                ('flag', models.BooleanField(blank=True, null=True)),
                ('material_leadtime', models.CharField(blank=True, choices=[('NA', 'NA'), ('TBA ', 'TBA '), ('Ex-stock', 'Ex-stock'), ('Ex-stock or 6 to 8 weeks', 'Ex-stock or 6 to 8 weeks'), ('Ex-stock or 8 to 12 weeks', 'Ex-stock or 8 to 12 weeks'), ('Ex-stock or 12 to 16 weeks', 'Ex-stock or 12 to 16 weeks'), ('3 to 4 weeks', '3 to 4 weeks'), ('6 to 8 weeks', '6 to 8 weeks'), ('8 to 12 weeks', '8 to 12 weeks'), ('12 to 16 weeks', '12 to 16 weeks'), ('16 to 20 weeks', '16 to 20 weeks')], default='NA', max_length=255, null=True)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('margin', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('totalgp', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('company_nameid', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.company')),
                ('contact_person', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.contact')),
                ('country', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='cities_light.country')),
            ],
            options={
                'db_table': 'tb_quotation',
            },
        ),
        migrations.CreateModel(
            name='SaleReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qtt_id', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('address', models.CharField(blank=True, max_length=100, null=True)),
                ('unit', models.CharField(blank=True, max_length=100, null=True)),
                ('postalcode', models.IntegerField(default=0)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('finaltotal', models.DecimalField(decimal_places=2, max_digits=8, null=True)),
                ('sale_person', models.CharField(blank=True, max_length=100, null=True)),
                ('RE', models.TextField(blank=True, null=True)),
                ('qtt_status', models.CharField(choices=[('Open', 'Open'), ('Awarded', 'Awarded'), ('Closed', 'Closed'), ('Loss', 'Loss')], default='Open', max_length=100)),
                ('sale_type', models.CharField(choices=[('Project', 'Project'), ('Maintenance', 'Maintenance'), ('Sales', 'Sales')], default='Project', max_length=100)),
                ('date', models.DateField(blank=True, null=True)),
                ('comment', models.TextField(blank=True, null=True)),
                ('comment_by', models.CharField(blank=True, max_length=100, null=True)),
                ('comment_at', models.DateField(blank=True, null=True)),
                ('margin', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('company_nameid', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.company')),
                ('contact_person', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.contact')),
                ('country', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='cities_light.country')),
                ('quotation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.quotation')),
            ],
            options={
                'db_table': 'tb_sale_report',
            },
        ),
        migrations.CreateModel(
            name='Salutation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, null=True, unique=True)),
            ],
            options={
                'db_table': 'tb_salutation',
            },
        ),
        migrations.CreateModel(
            name='Validity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'db_table': 'tb_validity',
            },
        ),
        migrations.CreateModel(
            name='Signature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signanture_name', models.CharField(blank=True, max_length=100, null=True)),
                ('company_stamp', models.ImageField(blank=True, upload_to=sales.models.content_file_signature)),
                ('signature_date', models.DateField(blank=True, null=True)),
                ('quotation', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.quotation')),
            ],
            options={
                'db_table': 'tb_signature',
            },
        ),
        migrations.CreateModel(
            name='Scope',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qtt_id', models.CharField(blank=True, max_length=100, null=True)),
                ('sn', models.CharField(blank=True, max_length=100, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('qty', models.IntegerField(blank=True, default=0, null=True)),
                ('unitprice', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('bal_qty', models.IntegerField(blank=True, default=0, null=True)),
                ('allocation_perc', models.CharField(blank=True, max_length=50, null=True)),
                ('unitcost', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('cost', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('gp', models.DecimalField(decimal_places=2, default=0, max_digits=20, null=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='sales.scope')),
                ('quotation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.quotation')),
                ('subject', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.parentsubject')),
                ('uom', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.uom')),
            ],
            options={
                'db_table': 'tb_scope',
            },
        ),
        migrations.CreateModel(
            name='SalesDOSignature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signature', jsignature.fields.JSignatureField(blank=True, null=True, verbose_name='Signature')),
                ('signature_date', models.DateTimeField(blank=True, null=True, verbose_name='Signature date')),
                ('name', models.CharField(blank=True, max_length=250, null=True)),
                ('nric', models.CharField(blank=True, max_length=250, null=True)),
                ('update_date', models.DateField(blank=True, null=True)),
                ('signature_image', models.ImageField(blank=True, null=True, upload_to=sales.models.content_file_dosignature)),
                ('do', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.productsalesdo')),
                ('product_sales', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.productsales')),
            ],
            options={
                'db_table': 'tb_product_sales_do_signature',
            },
        ),
        migrations.CreateModel(
            name='SaleReportComment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField(blank=True, null=True)),
                ('comment_by', models.CharField(blank=True, max_length=100, null=True)),
                ('comment_at', models.DateField(blank=True, null=True)),
                ('followup_date', models.DateField(blank=True, null=True)),
                ('salereport', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.salereport')),
            ],
            options={
                'db_table': 'tb_sale_report_comment',
            },
        ),
        migrations.CreateModel(
            name='QFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
                ('document', models.FileField(blank=True, upload_to=sales.models.content_file)),
                ('quotation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.quotation')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'tb_qfile',
            },
        ),
        migrations.CreateModel(
            name='ProductSalesDoItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(blank=True, max_length=250, null=True)),
                ('qty', models.IntegerField(blank=True, default=0, null=True)),
                ('do', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.productsalesdo')),
                ('product_sales', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.productsales')),
                ('uom', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.uom')),
            ],
            options={
                'db_table': 'tb_product_sales_do_items',
            },
        ),
        migrations.AddField(
            model_name='productsales',
            name='quotation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.quotation'),
        ),
        migrations.AddField(
            model_name='parentsubject',
            name='quotation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.quotation'),
        ),
        migrations.AddField(
            model_name='company',
            name='payment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.payment'),
        ),
        migrations.AddField(
            model_name='company',
            name='validity',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.validity'),
        ),
    ]