from django.conf import settings
from django.db import migrations


def wipe_locations(apps, schema_editor):
    """Wipe the old hierarchical location data before flattening.

    Locations are being redesigned from a self-referential hierarchy into a
    flat model tagged with independent Building/Block/Level dimensions. There
    is no clean automatic mapping, so (per product decision) we start fresh:

    * assets currently *held by* a location go back to IN_STOCK,
    * all location-holder assignment history + alerts are removed,
    * every asset's storage_location is cleared,
    * LOCATION assignees and all Location rows are deleted.

    Everything non-location (assets, people assignments and their history,
    catalogue, users) is untouched.

    This runs as its own migration so the deletes commit before the schema
    changes in 0004 (Postgres refuses to ALTER a table with pending trigger
    events from DML earlier in the same transaction).
    """
    Assignment = apps.get_model("assignments", "Assignment")
    InactiveHolderAlert = apps.get_model("assignments", "InactiveHolderAlert")
    Assignee = apps.get_model("assignees", "Assignee")
    AssetItem = apps.get_model("assets", "AssetItem")
    Location = apps.get_model("locations", "Location")

    loc_assignees = Assignee.objects.filter(assignee_type="LOCATION")

    # Assets whose current (open) holder is a location → return to stock.
    asset_ids = list(
        Assignment.objects.filter(
            assignee__in=loc_assignees, returned_at__isnull=True
        ).values_list("asset_id", flat=True)
    )
    if asset_ids:
        AssetItem.objects.filter(id__in=asset_ids).update(status="IN_STOCK")

    # Clear PROTECT-ing references, then the locations themselves.
    InactiveHolderAlert.objects.filter(assignee__in=loc_assignees).delete()
    Assignment.objects.filter(assignee__in=loc_assignees).delete()
    AssetItem.objects.filter(storage_location__isnull=False).update(storage_location=None)
    loc_assignees.delete()
    # Break the self-referential parent links (PROTECT) before bulk delete.
    Location.objects.exclude(parent__isnull=True).update(parent=None)
    Location.objects.all().delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("locations", "0002_location_block_level"),
        ("assignees", "0001_initial"),
        ("assignments", "0001_initial"),
        ("assets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(wipe_locations, noop),
    ]
