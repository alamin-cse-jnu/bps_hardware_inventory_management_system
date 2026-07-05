import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("locations", "0003_flatten_locations"),
    ]

    operations = [
        # ── New independent dimension lookups ─────────────────────────────────
        migrations.CreateModel(
            name="Building",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)ss_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Building", "verbose_name_plural": "Buildings", "ordering": ["name"], "abstract": False},
        ),
        migrations.CreateModel(
            name="Block",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)ss_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Block", "verbose_name_plural": "Blocks", "ordering": ["name"], "abstract": False},
        ),
        migrations.CreateModel(
            name="Level",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)ss_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Level", "verbose_name_plural": "Levels", "ordering": ["name"], "abstract": False},
        ),

        # ── Flatten Location ──────────────────────────────────────────────────
        migrations.AddField(
            model_name="location",
            name="building",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="locations", to="locations.building"),
        ),
        migrations.AddField(
            model_name="location",
            name="block",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="locations", to="locations.block"),
        ),
        migrations.AddField(
            model_name="location",
            name="level",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="locations", to="locations.level"),
        ),
        migrations.AddField(
            model_name="location",
            name="room",
            field=models.CharField(blank=True, max_length=100, default=""),
            preserve_default=False,
        ),
        migrations.RemoveField(model_name="location", name="parent"),
        migrations.RemoveField(model_name="location", name="level_type"),
        migrations.RemoveField(model_name="location", name="name_bn"),
        migrations.AlterModelOptions(
            name="location",
            options={"ordering": ["name"], "verbose_name": "Location", "verbose_name_plural": "Locations"},
        ),
    ]
