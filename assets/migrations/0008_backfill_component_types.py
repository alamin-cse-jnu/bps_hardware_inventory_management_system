"""
Phase 13 — seed ``catalogue.ComponentType`` from the legacy enum and link
every existing component row to its new master-data row.

The enum members become master data verbatim so nothing already recorded loses
its name. Only the two sized parts get unit chips; the rest are unsized, so
``capacity_required`` is off and the capacity box stays hidden for them. Every
seeded part is left unmapped (``applies_to`` empty) — mapping them to specific
Sub Assets is an Admin decision on the Master Data page, and an empty mapping
means "offered everywhere", which is exactly how the enum behaved.

Reverse unlinks the rows but keeps the seeded master data: deleting a part an
Admin may have since edited would lose more than this migration created.
"""

from django.db import migrations

# (code, name, units, capacity_required) — mirrors AssetComponent.ComponentType
# as of 0006. Frozen: later edits to that enum must not change this backfill.
SEED = [
    ("monitor",       "Monitor",       [],           False),
    ("keyboard",      "Keyboard",      [],           False),
    ("mouse",         "Mouse",         [],           False),
    ("cpu-unit",      "CPU Unit",      [],           False),
    ("ram",           "RAM",           ["GB"],       True),
    ("storage-drive", "Storage Drive", ["GB", "TB"], True),
    ("sfp",           "SFP Module",    [],           False),
    ("nic",           "Network Card",  [],           False),
    ("psu",           "Power Supply",  [],           False),
    ("battery",       "Battery",       [],           False),
    ("ups",           "UPS",           [],           False),
    ("other",         "Other",         [],           False),
]

# Legacy enum value -> seeded code
LEGACY = {
    "MONITOR": "monitor",
    "KEYBOARD": "keyboard",
    "MOUSE": "mouse",
    "CPU_UNIT": "cpu-unit",
    "RAM": "ram",
    "STORAGE_DRIVE": "storage-drive",
    "SFP": "sfp",
    "NIC": "nic",
    "PSU": "psu",
    "BATTERY": "battery",
    "UPS": "ups",
    "OTHER": "other",
}


def seed_and_link(apps, schema_editor):
    ComponentType = apps.get_model("catalogue", "ComponentType")
    AssetComponent = apps.get_model("assets", "AssetComponent")

    by_code = {}
    for order, (code, name, units, sized) in enumerate(SEED):
        row, _ = ComponentType.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "units": units,
                "default_unit": units[0] if units else "",
                "capacity_required": sized,
                "order": order,
            },
        )
        by_code[code] = row

    for legacy_value, code in LEGACY.items():
        AssetComponent.objects.filter(component_type=legacy_value, ctype__isnull=True).update(
            ctype=by_code[code]
        )

    # Anything carrying a value that never existed in the enum still needs a part.
    AssetComponent.objects.filter(ctype__isnull=True).update(ctype=by_code["other"])


def unlink(apps, schema_editor):
    apps.get_model("assets", "AssetComponent").objects.update(ctype=None)


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0007_component_procurement_fields"),
        ("catalogue", "0003_componenttype"),
    ]

    operations = [
        migrations.RunPython(seed_and_link, unlink),
    ]
