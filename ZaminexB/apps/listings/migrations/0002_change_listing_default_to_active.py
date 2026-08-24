# Generated migration – changes Listing.status default from DRAFT to ACTIVE

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="listing",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("ACTIVE", "Active"),
                    ("PAUSED", "Paused"),
                    ("EXPIRED", "Expired"),
                    ("ARCHIVED", "Archived"),
                ],
                default="ACTIVE",
                max_length=20,
            ),
        ),
    ]
