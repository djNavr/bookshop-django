from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='sortkod',
            field=models.CharField(blank=True, null=True, unique=True, max_length=50),
        ),
        migrations.AddField(
            model_name='book',
            name='ean',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='book',
            name='isbn',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='book',
            name='stock',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='book',
            name='available',
            field=models.BooleanField(default=True),
        ),
    ]
