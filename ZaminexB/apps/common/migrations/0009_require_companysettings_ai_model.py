from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0008_alter_companysettings_ai_model"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companysettings",
            name="ai_model",
            field=models.CharField(
                help_text="شناسه مدل سرویس‌دهنده الزامی است؛ مثلاً gpt-4o-mini، deepseek-chat، gemini-1.5-flash.",
                max_length=200,
                verbose_name="نام مدل",
            ),
        ),
    ]
