
import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_consultantprofile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consultantprofile',
            name='hired_at',
            field=models.DateField(default=datetime.date.today),
        ),
        migrations.AlterField(
            model_name='consultantprofile',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
