
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsultantProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255)),
                ('mobile', models.CharField(max_length=11, unique=True, validators=[django.core.validators.RegexValidator(message='Enter a valid Iranian mobile number.', regex='^09\\d{9}$')])),
                ('branch', models.CharField(max_length=255)),
                ('profile_image', models.ImageField(blank=True, null=True, upload_to='consultants/profile/')),
                ('hired_at', models.DateField()),
                ('notes', models.TextField(blank=True)),
                ('is_active', models.BooleanField()),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='consultant_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Consultant Profile',
                'verbose_name_plural': 'Consultant Profiles',
                'ordering': ['full_name'],
            },
        ),
    ]
