from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0011_abandoned_cart'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopconfig',
            name='sender_email',
            field=models.EmailField(
                blank=True,
                help_text='E-mailova adresa odesilatele pro systemove zpravy.',
                null=True,
                verbose_name='email address',
            ),
        ),
    ]
