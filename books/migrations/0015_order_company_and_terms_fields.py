from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0014_shopconfig_free_shipping_threshold'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='company_id',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='order',
            name='company_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='order',
            name='is_company_order',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='order',
            name='terms_accepted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='order',
            name='terms_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='vat_id',
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
