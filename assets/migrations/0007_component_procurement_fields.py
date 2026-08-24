"""
Phase 13 — component procurement fields.

Adds the master-data link (``ctype``), the size of the part
(``capacity``/``unit``) and what it cost (``cost``/``vendor``/
``purchase_date``/``purchase_order``). ``component_type`` is deliberately left
in place and is backfilled alongside ``ctype`` by 0008, so rows written before
this phase still name their part.

NOTE: ``makemigrations`` will try to fold the parked
``uniq_live_asset_serial_ci`` constraint into any new assets migration, because
the constraint is declared on the model but its migration is parked (see
``_pending_0007_uniq_live_asset_serial_ci.py``). It is left out here on
purpose — applying it before the duplicate serials are cleaned would fail
``migrate`` and take the web container down with it. Drop that operation again
if a future run re-adds it.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0006_alter_assetcomponent_component_type"),
        ("catalogue", "0003_componenttype"),
    ]

    operations = [
        migrations.AddField(
            model_name="assetcomponent",
            name="ctype",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="components",
                to="catalogue.componenttype",
            ),
        ),
        migrations.AddField(
            model_name="assetcomponent",
            name="capacity",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="assetcomponent",
            name="unit",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="assetcomponent",
            name="cost",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="assetcomponent",
            name="vendor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="components",
                to="assets.vendor",
            ),
        ),
        migrations.AddField(
            model_name="assetcomponent",
            name="purchase_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="assetcomponent",
            name="purchase_order",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
