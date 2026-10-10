from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0012_ticket_choices"),
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name="AIInsightCache")],
            database_operations=[],
        ),
    ]
