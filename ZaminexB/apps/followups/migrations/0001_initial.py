
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('properties', '0003_propertyimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='FollowUp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('follow_up_type', models.CharField(choices=[('Call', 'Call'), ('Meeting', 'Meeting'), ('Email', 'Email'), ('Site Visit', 'Site Visit')], default='Call', max_length=20)),
                ('contact_name', models.CharField(max_length=255)),
                ('scheduled_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('consultant_name', models.CharField(blank=True, max_length=255)),
                ('property_title', models.CharField(blank=True, max_length=255, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('outcome', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('completed', 'Completed')], default='scheduled', max_length=20)),
                ('probability', models.PositiveSmallIntegerField(blank=True, help_text='Probability of closing from 0 to 100', null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('is_archived', models.BooleanField(default=False)),
                ('archived_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('consultant', models.ForeignKey(limit_choices_to={'role': 'AGENT'}, on_delete=django.db.models.deletion.PROTECT, related_name='followups', to=settings.AUTH_USER_MODEL)),
                ('property', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='followups', to='properties.property')),
            ],
            options={
                'verbose_name': 'Follow-Up',
                'verbose_name_plural': 'Follow-Ups',
                'ordering': ['scheduled_at', '-created_at'],
                'indexes': [models.Index(fields=['consultant', 'status'], name='followups_f_consult_b763f8_idx'), models.Index(fields=['property'], name='followups_f_propert_23ae1d_idx'), models.Index(fields=['scheduled_at'], name='followups_f_schedul_c295a1_idx'), models.Index(fields=['is_archived'], name='followups_f_is_arch_0d3888_idx')],
            },
        ),
    ]
