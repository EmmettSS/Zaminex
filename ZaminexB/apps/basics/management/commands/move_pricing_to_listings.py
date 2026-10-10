from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.basics.models import DealType
from apps.listings.models import Listing
from apps.properties.models import Property

RENTAL_DEAL_TYPES = {"mortgage_rent", "full_mortgage"}


class Command(BaseCommand):
    help = "Copy legacy Property.price onto the matching Listing pricing columns."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def _apply_price(self, listing, price, deal_name):
        if deal_name in RENTAL_DEAL_TYPES:
            listing.deposit = price
        else:
            listing.sale_price = price

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING("\nانتقال قیمت از ملک به آگهی"))

        updated = created = skipped = 0

        for prop in Property.objects.prefetch_related("listings__deal_type"):
            price = prop.price
            if not price:
                continue

            listings = list(prop.listings.all())

            if listings:
                for listing in listings:
                    if listing.sale_price or listing.deposit or listing.monthly_rent:
                        skipped += 1
                        continue

                    deal_name = listing.deal_type.name if listing.deal_type else "sale"
                    self._apply_price(listing, price, deal_name)

                    if not dry_run:
                        listing.save(
                            update_fields=[
                                "sale_price",
                                "deposit",
                                "monthly_rent",
                                "updated_at",
                            ]
                        )
                    updated += 1
                    self.stdout.write(
                        f"    آگهی #{listing.id} ({deal_name}) ← {price:,.0f}"
                    )
            else:
                deal_name = "mortgage_rent" if prop.deal_type == "RENT" else "sale"
                deal_type = DealType.objects.filter(name=deal_name).first()

                listing = Listing(
                    property=prop,
                    title=prop.title,
                    description=prop.description or "",
                    deal_type=deal_type,
                    publish_channel=Listing.PublishChannel.WEBSITE,
                    status=Listing.Status.DRAFT,
                    created_by=prop.consultant,
                    assigned_to=prop.consultant,
                    start_date=timezone.now(),
                )
                self._apply_price(listing, price, deal_name)

                if not dry_run:
                    listing.save()
                created += 1
                self.stdout.write(
                    f"    ملک #{prop.id} «{prop.title[:24]}» ← آگهی جدید ({deal_name}) {price:,.0f}"
                )

        self.stdout.write(
            f"\n  {updated} آگهی به‌روزرسانی شد، {created} آگهی ساخته شد، "
            f"{skipped} آگهی از قبل قیمت داشت"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\nاجرای آزمایشی — چیزی ذخیره نشد."))
            transaction.set_rollback(True)
            return

        self.stdout.write(self.style.SUCCESS("\nانتقال قیمت انجام شد."))
