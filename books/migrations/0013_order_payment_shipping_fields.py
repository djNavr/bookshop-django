from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0012_shopconfig_sender_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='paid_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_details',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_reference',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(choices=[('pending', 'Čeká na platbu'), ('authorized', 'Platba autorizována'), ('paid', 'Zaplaceno'), ('failed', 'Platba selhala'), ('refunded', 'Vráceno'), ('manual_review', 'Ruční kontrola')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_transaction_id',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='pickup_point_code',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='pickup_point_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_details',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_method',
            field=models.CharField(blank=True, choices=[('zasilkovna', 'Zásilkovna - výdejní místo'), ('ppl', 'PPL kurýr'), ('balikovna', 'Balíkovna'), ('gls', 'GLS kurýr'), ('external_dispatch', 'Externí zajištění dopravy')], max_length=32),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_status',
            field=models.CharField(choices=[('pending', 'Čeká na zpracování'), ('preparing', 'Připravuje se'), ('handed_over', 'Předáno dopravci'), ('delivered', 'Doručeno'), ('cancelled', 'Doprava zrušena')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_tracking_code',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_tracking_url',
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(blank=True, choices=[('bank_transfer', 'Bankovní převod'), ('qr_payment', 'Platba přes QR'), ('benefit_card', 'Benefitní karta'), ('invoice', 'Platba na fakturu'), ('gopay', 'GoPay'), ('comgate', 'Comgate'), ('stripe', 'Stripe'), ('cash_on_delivery', 'Dobírka')], max_length=32),
        ),
    ]
