from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0002_book_catalog_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='currency',
            field=models.CharField(default='CZK', max_length=8),
            preserve_default=False,
        ),
    ]
