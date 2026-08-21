
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='property',
            name='status',
            field=models.CharField(choices=[('AVAILABLE', 'Available'), ('RESERVED', 'Reserved'), ('SOLD', 'Sold'), ('INACTIVE', 'Archived')], default='AVAILABLE', max_length=20),
        ),
    ]
