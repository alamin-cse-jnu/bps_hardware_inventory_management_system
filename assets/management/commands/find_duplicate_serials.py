"""
Report live assets that share a serial number.

Run this before applying the ``uniq_live_asset_serial_ci`` constraint migration
on a database with existing data — the migration cannot be applied while any
duplicate remains, and this names the rows that have to be fixed first.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import Upper

from assets.models import NON_SERIAL_PLACEHOLDERS, AssetItem


class Command(BaseCommand):
    help = "List live assets sharing a serial number (case-insensitive)."

    def handle(self, *args, **options):
        groups = (
            AssetItem.objects.filter(is_deleted=False)
            .exclude(serial_number="")
            .annotate(key=Upper("serial_number"))
            # Placeholders mean "no serial" and are exempt from uniqueness.
            .exclude(key__in=sorted(NON_SERIAL_PLACEHOLDERS))
            .values("key")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("-n", "key")
        )

        total = 0
        for group in groups:
            assets = (
                AssetItem.objects.filter(is_deleted=False, serial_number__iexact=group["key"])
                .order_by("asset_tag")
            )
            self.stdout.write(self.style.WARNING(f"\n{group['key']} — {group['n']} assets"))
            for asset in assets:
                self.stdout.write(
                    f"  {asset.asset_tag}  {asset.brand} {asset.model_name}  "
                    f"[{asset.get_status_display()}]  serial={asset.serial_number!r}"
                )
            total += 1

        if total:
            self.stdout.write(
                self.style.ERROR(
                    f"\n{total} duplicated serial number(s). Correct or soft-delete the "
                    "extra rows before migrating."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("No duplicate serial numbers."))
