from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0002_alter_task_options_alter_task_assigned_to_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="note",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Free-form internal note added from the task detail modal",
                verbose_name="یادداشت",
            ),
        ),
    ]
