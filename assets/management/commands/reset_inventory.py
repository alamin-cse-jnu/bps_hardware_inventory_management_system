"""
Management command: reset_inventory

Wipes operational inventory data to a clean slate for testing / go-live:
  - All assets (items + components) and their history
    (assignments, lifecycle events, audit scans/sessions, alerts, transfer batches)
  - All holders (CachedEmployee / CachedMP / CachedOffice + unified Assignee rows)
  - All locations (building / floor / room)

KEEPS the catalog and config:
  - AssetCategory, AssetType, Brand, Vendor, AssetModelName, SpecChoice, WorkOrder
  - Users, Groups, SyncLog

This is a HARD delete (rows are permanently removed), intentionally bypassing
the normal soft-delete convention — it exists only for resetting a test/blank
environment. Deletion order respects every on_delete=PROTECT foreign key.

Usage:
    python manage.py reset_inventory            # dry run — shows what WOULD be deleted
    python manage.py reset_inventory --confirm  # actually delete (single transaction)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from assets.models import AssetItem, AssetComponent
from assignments.models import Assignment, TransferBatch, InactiveHolderAlert
from qrcodes.models import AuditSession, AuditScan
from lifecycle.models import LifecycleEvent
from assignees.models import Assignee, CachedEmployee, CachedMP, CachedOffice
from locations.models import Location


class Command(BaseCommand):
    help = "Wipe assets, holders, and locations (keeps catalog/types). Dry-run unless --confirm."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Actually perform the deletion. Without this flag, only a dry-run summary is shown.",
        )

    def handle(self, *args, **options):
        # Ordered so each step removes rows that PROTECT-reference the next target.
        # (label, queryset) — counted before any deletion happens.
        steps = [
            ("Inactive holder alerts", InactiveHolderAlert.objects.all()),
            ("Audit scans",            AuditScan.objects.all()),
            ("Audit sessions",         AuditSession.objects.all()),
            ("Lifecycle events",       LifecycleEvent.objects.all()),
            ("Assignments",            Assignment.objects.all()),
            ("Transfer batches",       TransferBatch.objects.all()),
            ("Asset components",       AssetComponent.objects.all()),
            ("Assets",                 AssetItem.objects.all()),
            ("Assignees (unified)",    Assignee.objects.all()),
            ("Cached employees",       CachedEmployee.objects.all()),
            ("Cached MPs",             CachedMP.objects.all()),
            ("Cached offices",         CachedOffice.objects.all()),
            # Locations deleted children-first because Location.parent is PROTECT.
            ("Locations — rooms",      Location.objects.filter(level_type=Location.LevelType.ROOM)),
            ("Locations — floors",     Location.objects.filter(level_type=Location.LevelType.FLOOR)),
            ("Locations — buildings",  Location.objects.filter(level_type=Location.LevelType.BUILDING)),
        ]

        counts = [(label, qs.count()) for label, qs in steps]
        total = sum(c for _, c in counts)

        self.stdout.write(self.style.MIGRATE_HEADING("\nWill DELETE:"))
        for label, count in counts:
            self.stdout.write(f"  {label:.<32} {count:>6}")
        self.stdout.write(f"  {'TOTAL rows':.<32} {total:>6}")

        self.stdout.write(self.style.MIGRATE_HEADING("\nWill KEEP:"))
        for label in ("Asset categories", "Asset types", "Brands", "Vendors",
                      "Model names", "Spec choices", "Work orders", "Users / Groups", "Sync logs"):
            self.stdout.write(f"  {label}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("\nNothing to delete — already clean.\n"))
            return

        if not options["confirm"]:
            self.stdout.write(self.style.WARNING(
                "\nDRY RUN — nothing deleted. Re-run with --confirm to apply.\n"
            ))
            return

        with transaction.atomic():
            for label, qs in steps:
                deleted, _ = qs.delete()
                self.stdout.write(f"  deleted {label} ({deleted} rows incl. cascades)")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Wiped {total} inventory rows. Catalog/types preserved.\n"
        ))
