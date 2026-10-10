from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_alter_adminprofile_branch_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('ADMIN', 'مدیر'), ('AGENT', 'مشاور')], db_index=True, default='AGENT', max_length=20, verbose_name='نقش کاربری'),
        ),
    ]
