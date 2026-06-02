from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0003_book_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='book_type',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='book',
            name='category',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
