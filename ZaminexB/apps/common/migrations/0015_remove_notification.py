from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0014_remove_activitylog"),
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name="Notification")],
            database_operations=[],
        ),
    ]
