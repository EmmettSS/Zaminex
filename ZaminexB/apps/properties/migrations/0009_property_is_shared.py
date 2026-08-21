
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0008_property_district_alter_property_neighborhood'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='is_shared',
            field=models.BooleanField(
                default=False,
                help_text='وقتی فعال باشد، همه مشاوران ملک را می‌بینند و می‌توانند ویرایش کنند (به جز تغییر مشاور مسئول).',
                verbose_name='نمایش برای همه مشاوران',
            ),
        ),
    ]
