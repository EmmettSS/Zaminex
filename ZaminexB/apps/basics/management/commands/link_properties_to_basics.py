from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.basics.models import DealType, PropertyType
from apps.listings.models import Listing
from apps.properties.models import Property

PROPERTY_TYPE_MAP = {
    "APARTMENT": "apartment",
    "VILLA": "villa",
    "TOWNHOUSE": "townhouse",
    "STUDIO": "studio",
    "PENTHOUSE": "penthouse",
    "COMMERCIAL": "commercial",
    "OFFICE": "office",
    "SHOP": "shop",
    "LAND": "land",
    "OTHER": "other",
}

DEAL_TYPE_MAP = {
    "SALE": "sale",
    "RENT": "mortgage_rent",
}


class Command(BaseCommand):
    help = "Link existing properties and listings to the new reference-data tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        types = {t.name: t for t in PropertyType.objects.all()}
        deals = {d.name: d for d in DealType.objects.all()}

        if not types or not deals:
            raise CommandError(
                "جداول اطلاعات پایه خالی است. ابتدا این دستور را اجرا کنید:\n"
                "  python manage.py seed_basics"
            )

        missing = [
            target for target in set(PROPERTY_TYPE_MAP.values()) if target not in types
        ] + [target for target in set(DEAL_TYPE_MAP.values()) if target not in deals]
        if missing:
            raise CommandError(
                "این رکوردهای پایه پیدا نشدند: " + "، ".join(sorted(missing))
                + "\nابتدا `python manage.py seed_basics` را اجرا کنید."
            )

        self.stdout.write(self.style.MIGRATE_HEADING("\nاتصال املاک به اطلاعات پایه"))

        linked = skipped = 0
        unmapped: list[tuple[int, str]] = []

        for prop in Property.objects.select_related(
            "property_type_ref", "property_usage"
        ):
            if prop.property_type_ref_id:
                skipped += 1
                continue

            target = PROPERTY_TYPE_MAP.get((prop.property_type or "").upper())
            if not target:
                unmapped.append((prop.id, prop.property_type or "—"))
                continue

            type_obj = types[target]
            if not dry_run:
                Property.objects.filter(pk=prop.pk).update(
                    property_type_ref=type_obj,
                    property_usage=type_obj.property_usage,
                )
            linked += 1
            self.stdout.write(
                f"    #{prop.id} {prop.title[:28]:28} "
                f"{prop.property_type:10} → {type_obj.display_name} "
                f"({type_obj.property_usage.display_name})"
            )

        self.stdout.write(
            f"  املاک: {linked} متصل شد، {skipped} از قبل متصل بود"
        )
        if unmapped:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! {len(unmapped)} ملک با نوع ناشناخته: "
                    + "، ".join(f"#{pk}({value})" for pk, value in unmapped)
                )
            )

        listing_linked = listing_skipped = 0
        listing_unmapped: list[tuple[int, str]] = []

        for listing in Listing.objects.select_related("property", "deal_type"):
            if listing.deal_type_id:
                listing_skipped += 1
                continue

            source = (listing.property.deal_type or "").upper() if listing.property else ""
            target = DEAL_TYPE_MAP.get(source)
            if not target:
                listing_unmapped.append((listing.id, source or "—"))
                continue

            if not dry_run:
                Listing.objects.filter(pk=listing.pk).update(deal_type=deals[target])
            listing_linked += 1

        self.stdout.write(
            f"  آگهی‌ها: {listing_linked} متصل شد، {listing_skipped} از قبل متصل بود"
        )
        if listing_unmapped:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! {len(listing_unmapped)} آگهی بدون نوع معامله: "
                    + "، ".join(f"#{pk}({value})" for pk, value in listing_unmapped)
                )
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nاجرای آزمایشی — هیچ تغییری ذخیره نشد.")
            )
            transaction.set_rollback(True)
            return

        remaining = Property.objects.filter(property_type_ref__isnull=True).count()
        if remaining:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{remaining} ملک هنوز به نوع ملک متصل نیست "
                    "(نوع نامعتبر در داده قدیمی)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\nهمهٔ املاک و آگهی‌ها به اطلاعات پایه متصل شدند.")
            )
