from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0013_order_payment_shipping_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopconfig',
            name='free_shipping_threshold',
            field=models.DecimalField(
                decimal_places=2,
                default=1500,
                help_text='Minimalni hodnota objednavky pro dopravu zdarma (v CZK).',
                max_digits=10,
            ),
        ),
    ]
