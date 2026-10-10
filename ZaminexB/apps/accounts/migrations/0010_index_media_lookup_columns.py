from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_alter_user_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminprofile',
            name='profile_image',
            field=models.ImageField(blank=True, db_index=True, null=True, upload_to='admins/profile/', verbose_name='تصویر پروفایل'),
        ),
        migrations.AlterField(
            model_name='consultantprofile',
            name='profile_image',
            field=models.ImageField(blank=True, db_index=True, null=True, upload_to='consultants/profile/', verbose_name='تصویر پروفایل'),
        ),
    ]
