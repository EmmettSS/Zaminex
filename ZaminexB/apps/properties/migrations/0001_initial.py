
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('internal_code', models.CharField(max_length=50, unique=True)),
                ('property_type', models.CharField(choices=[('APARTMENT', 'Apartment'), ('VILLA', 'Villa'), ('OFFICE', 'Office'), ('SHOP', 'Shop'), ('LAND', 'Land'), ('OTHER', 'Other')], max_length=20)),
                ('deal_type', models.CharField(choices=[('SALE', 'Sale'), ('RENT', 'Rent')], max_length=20)),
                ('price', models.DecimalField(decimal_places=0, max_digits=18)),
                ('area', models.PositiveIntegerField()),
                ('rooms', models.PositiveIntegerField(default=0)),
                ('floor', models.IntegerField(blank=True, null=True)),
                ('built_year', models.PositiveIntegerField(blank=True, null=True)),
                ('address', models.TextField()),
                ('neighborhood', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('status', models.CharField(choices=[('AVAILABLE', 'Available'), ('RESERVED', 'Reserved'), ('SOLD', 'Sold'), ('INACTIVE', 'Inactive')], default='AVAILABLE', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('consultant', models.ForeignKey(limit_choices_to={'role': 'AGENT'}, on_delete=django.db.models.deletion.PROTECT, related_name='properties', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
