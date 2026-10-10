from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0013_remove_aiinsightcache"),
        ("activity", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name="ActivityLog")],
            database_operations=[],
        ),
    ]
