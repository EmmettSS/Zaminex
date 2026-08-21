"""Move the flat district list into the Province → City → District hierarchy.

Before phase 4 a district was a single free-text name (`common.District`) and
`Property.neighborhood` stored an unvalidated string. Both are replaced by a
real hierarchy so an agency can describe its coverage area properly.

The agency owns its own geography, so nothing is invented: no province or city
list is shipped. Existing data still has to land somewhere, though, so this
command groups every district found in the old table and on existing properties
under one province/city that the operator names explicitly.

    # Preview — writes nothing
    python manage.py migrate_districts_to_hierarchy \
        --province "مازندران" --city "ساری" --dry-run

    # Apply
    python manage.py migrate_districts_to_hierarchy \
        --province "مازندران" --city "ساری"

Afterwards an administrator adds the real provinces and cities from the
"مدیریت مناطق" screen and can move districts across with a normal edit.

Idempotent: properties that already point at a district are left alone, so it is
safe to re-run after adding more legacy rows.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.basics.models import City, District, Province
from apps.common.models import District as LegacyDistrict
from apps.properties.models import Property


def _slug(value: str) -> str:
    """A URL-safe slug that keeps Persian characters readable."""
    return slugify(value, allow_unicode=True) or None


class Command(BaseCommand):
    help = "Migrate flat districts and property neighbourhoods into Province → City → District."

    def add_arguments(self, parser):
        parser.add_argument(
            "--province",
            required=True,
            help="Province to file the existing districts under (e.g. مازندران).",
        )
        parser.add_argument(
            "--city",
            required=True,
            help="City to file the existing districts under (e.g. ساری).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        province_name = options["province"].strip()
        city_name = options["city"].strip()
        dry_run = options["dry_run"]

        if not province_name or not city_name:
            raise CommandError("نام استان و شهر نمی‌تواند خالی باشد.")

        self.stdout.write(
            self.style.MIGRATE_HEADING("\nانتقال محله‌ها به ساختار استان / شهر / محله")
        )
        self.stdout.write(f"  استان مقصد: {province_name}")
        self.stdout.write(f"  شهر مقصد  : {city_name}")

        # --- province & city --------------------------------------------------
        province = Province.objects.filter(display_name=province_name).first()
        if province is None:
            province = Province(
                name=_slug(province_name) or "province",
                display_name=province_name,
                slug=_slug(province_name),
            )
            if not dry_run:
                province.save()
            self.stdout.write(f"  + استان «{province_name}» ایجاد شد")
        else:
            self.stdout.write(f"  = استان «{province_name}» از قبل موجود بود")

        city = None
        if province.pk:
            city = City.objects.filter(province=province, display_name=city_name).first()
        if city is None:
            city = City(
                province=province,
                name=_slug(city_name) or "city",
                display_name=city_name,
                slug=_slug(city_name),
            )
            if not dry_run:
                city.save()
            self.stdout.write(f"  + شهر «{city_name}» ایجاد شد")
        else:
            self.stdout.write(f"  = شهر «{city_name}» از قبل موجود بود")

        # --- collect every distinct neighbourhood name ------------------------
        names: list[str] = []

        for legacy in LegacyDistrict.objects.all():
            label = (legacy.name or "").strip()
            if label and label not in names:
                names.append(label)

        for value in (
            Property.objects.filter(district__isnull=True)
            .exclude(neighborhood="")
            .values_list("neighborhood", flat=True)
        ):
            label = (value or "").strip()
            if label and label not in names:
                names.append(label)

        if not names:
            self.stdout.write(self.style.WARNING("\n  محله‌ای برای انتقال یافت نشد."))
            if dry_run:
                transaction.set_rollback(True)
            return

        # --- create the districts ---------------------------------------------
        self.stdout.write(f"\n  {len(names)} محله برای انتقال:")
        districts: dict[str, District] = {}
        created = reused = 0

        for index, label in enumerate(names, start=1):
            existing = None
            if city.pk:
                existing = District.objects.filter(city=city, display_name=label).first()

            if existing is not None:
                districts[label] = existing
                reused += 1
                self.stdout.write(f"    = {label}")
                continue

            district = District(
                city=city,
                name=_slug(label) or f"district-{index}",
                display_name=label,
                slug=_slug(f"{city_name}-{label}"),
                sort_order=index * 10,
            )
            if not dry_run:
                district.save()
            districts[label] = district
            created += 1
            self.stdout.write(f"    + {label}")

        # --- point properties at their district --------------------------------
        linked = skipped = 0
        for prop in Property.objects.filter(district__isnull=True):
            label = (prop.neighborhood or "").strip()
            district = districts.get(label)
            if district is None or not district.pk:
                skipped += 1
                continue
            if not dry_run:
                # update() avoids re-triggering save() (which would just rewrite
                # the same neighbourhood text back).
                Property.objects.filter(pk=prop.pk).update(district=district)
            linked += 1

        self.stdout.write(
            f"\n  محله‌ها: {created} ایجاد، {reused} موجود"
            f"\n  املاک  : {linked} متصل شد"
            + (f"، {skipped} بدون محله" if skipped else "")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\nاجرای آزمایشی — چیزی ذخیره نشد."))
            transaction.set_rollback(True)
            return

        remaining = (
            Property.objects.filter(district__isnull=True).exclude(neighborhood="").count()
        )
        if remaining:
            self.stdout.write(
                self.style.WARNING(f"\n  {remaining} ملک هنوز به محله متصل نیست.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nانتقال محله‌ها انجام شد."))
