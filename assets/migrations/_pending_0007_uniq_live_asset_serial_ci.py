"""
PARKED — not applied yet. Django's migration loader skips modules whose name
starts with "_", so this file is inert until it is renamed to
``0007_assetitem_uniq_live_asset_serial_ci.py``.

It is parked because the constraint cannot be created while duplicate serials
exist, and the web container runs ``migrate`` before gunicorn — a failing
migration takes the whole site down with a 502 rather than just refusing the
index. Clean the data first:

    python manage.py find_duplicate_serials      # must report none
    mv assets/migrations/_pending_0007_uniq_live_asset_serial_ci.py \
       assets/migrations/0007_assetitem_uniq_live_asset_serial_ci.py
    python manage.py migrate

Form, bulk-add and Excel-import validation are unaffected by the parking —
they run in application code and are already live.

Make serial numbers unique across live assets.

A pre-check runs first: PostgreSQL would reject the index with a bare
"could not create unique index" if any duplicate is already stored, so the
check turns that into a message naming the count and pointing at the
``find_duplicate_serials`` command. No data is changed here — deciding which of
two rows carrying the same serial is the wrong one is not the migration's call.

The constraint skips blanks and the "no serial" placeholder words, which are
allowed to repeat; the pre-check uses the same exemption list so the two agree.
"""
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models

# Frozen copy of assets.models.NON_SERIAL_PLACEHOLDERS as it stood for this
# migration — later edits to that set must not change what this one enforced.
PLACEHOLDERS = [
    "-", "--", ".", "?", "N/A", "NA", "NIL", "NONE",
    "NOT AVAILABLE", "NOT SPECIFIED", "UNKNOWN",
]


def check_no_duplicate_serials(apps, schema_editor):
    from django.db.models import Count
    from django.db.models.functions import Upper

    AssetItem = apps.get_model("assets", "AssetItem")
    duplicates = (
        AssetItem.objects.filter(is_deleted=False)
        .exclude(serial_number="")
        .annotate(key=Upper("serial_number"))
        .exclude(key__in=PLACEHOLDERS)
        .values("key")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .order_by("-n", "key")
    )
    keys = [row["key"] for row in duplicates]
    if not keys:
        return

    sample = ", ".join(keys[:10])
    more = f" (and {len(keys) - 10} more)" if len(keys) > 10 else ""
    raise RuntimeError(
        f"{len(keys)} serial number(s) are used by more than one live asset, so the "
        f"uniqueness constraint cannot be applied: {sample}{more}.\n"
        "Run `python manage.py find_duplicate_serials` to list the assets involved, "
        "then correct or soft-delete the extra rows and migrate again."
    )


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0006_alter_assetcomponent_component_type'),
        ('locations', '0004_location_dimensions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(check_no_duplicate_serials, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='assetitem',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Upper('serial_number'), condition=models.Q(('is_deleted', False), models.Q(('serial_number', ''), _negated=True), models.Q(('serial_number__iexact', '-'), _negated=True), models.Q(('serial_number__iexact', '--'), _negated=True), models.Q(('serial_number__iexact', '.'), _negated=True), models.Q(('serial_number__iexact', '?'), _negated=True), models.Q(('serial_number__iexact', 'N/A'), _negated=True), models.Q(('serial_number__iexact', 'NA'), _negated=True), models.Q(('serial_number__iexact', 'NIL'), _negated=True), models.Q(('serial_number__iexact', 'NONE'), _negated=True), models.Q(('serial_number__iexact', 'NOT AVAILABLE'), _negated=True), models.Q(('serial_number__iexact', 'NOT SPECIFIED'), _negated=True), models.Q(('serial_number__iexact', 'UNKNOWN'), _negated=True)), name='uniq_live_asset_serial_ci', violation_error_message='This serial number is already used by another asset. Serial numbers must be unique.'),
        ),
    ]
