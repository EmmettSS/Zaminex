from decimal import Decimal

from django.db import migrations, models

from apps.basics.categorization import ESSENTIAL, NON_ESSENTIAL

BUILTIN_CATEGORIES = (
    (ESSENTIAL, "ویژگی ضروری", Decimal("1")),
    (NON_ESSENTIAL, "ویژگی غیر ضروری", Decimal("2")),
)


def seed_builtin_categories(apps, schema_editor):
    AttributeCategory = apps.get_model("basics", "AttributeCategory")

    for name, display_name, sort_order in BUILTIN_CATEGORIES:
        category, created = AttributeCategory.objects.get_or_create(
            name=name,
            defaults={
                "display_name": display_name,
                "sort_order": sort_order,
                "is_active": True,
            },
        )
        if not created and (
            category.deleted_at is not None
            or not category.is_active
            or category.display_name != display_name
        ):
            category.deleted_at = None
            category.is_active = True
            category.display_name = display_name
            category.sort_order = sort_order
            category.save(
                update_fields=[
                    "deleted_at",
                    "is_active",
                    "display_name",
                    "sort_order",
                    "updated_at",
                ]
            )


def remove_builtin_categories(apps, schema_editor):
    AttributeCategory = apps.get_model("basics", "AttributeCategory")
    AttributeCategory.objects.filter(
        name__in=[name for name, _, _ in BUILTIN_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("basics", "0003_attribute_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="AttributeCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="تاریخ ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="فعال")),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="تاریخ حذف")),
                ("name", models.CharField(db_index=True, help_text="شناسه انگلیسی و ثابت (مانند apartment). پس از ایجاد تغییر نکند.", max_length=100, verbose_name="کلید سیستمی")),
                ("display_name", models.CharField(max_length=255, verbose_name="نام نمایشی")),
                ("sort_order", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="ترتیب نمایش")),
                ("meta_data", models.JSONField(blank=True, default=dict, verbose_name="متادیتا")),
            ],
            options={
                "verbose_name": "دسته\u200cبندی ویژگی",
                "verbose_name_plural": "دسته\u200cبندی\u200cهای ویژگی",
                "db_table": "basics_attribute_category",
                "ordering": ["sort_order", "display_name"],
                "abstract": False,
                "constraints": [models.UniqueConstraint(condition=models.Q(("deleted_at__isnull", True)), fields=("name",), name="uq_attribute_category_name_alive")],
            },
        ),
        migrations.AlterField(
            model_name="attribute",
            name="category",
            field=models.CharField(db_index=True, default="non_essential", help_text="دسته\u200cبندی\u200cای که این ویژگی در آن قرار می\u200cگیرد؛ فهرست دسته\u200cبندی\u200cها از تب «دسته\u200cبندی ویژگی\u200cها» مدیریت می\u200cشود. یک ویژگی همیشه دقیقاً در یک دسته\u200cبندی قرار دارد.", max_length=100, verbose_name="دسته\u200cبندی ویژگی"),
        ),
        migrations.RunPython(seed_builtin_categories, remove_builtin_categories),
    ]
