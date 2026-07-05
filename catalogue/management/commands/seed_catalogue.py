"""
Seed the master-data catalogue from the polished Excel workbook.

Idempotent: re-running matches existing rows by name (case-insensitive) rather
than creating duplicates. Populates Main Assets (AssetCategory), Sub Assets
(AssetType), Brands, Models, and a sensible structured spec-field schema per Sub
Asset (derived from the workbook's specification templates).

    python manage.py seed_catalogue [--path docs/Asset_Master_Data_Polished.xlsx]
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from assets.models import AssetCategory, AssetType
from catalogue.models import CatalogBrand, CatalogModel, SubAssetSpecField
from catalogue.specs import slugify_key


# Structured spec schema per Sub Asset name. Each field: (label, widget, unit, options).
# Widgets: text | number | units | select | toggle
#
# STANDARDIZATION RULE (one field = one atomic attribute):
#   Never pack brand + generation + series/model + capacity into a single field.
#   Name each field "<Component> <Attribute>" (e.g. Processor Brand / Processor
#   Series / Processor Generation). Use toggle/select for controlled vocabularies,
#   units for quantity+unit, number for a value with one fixed unit, text only for
#   genuinely free-form values. Order attributes of a component contiguously, most-
#   to least-significant. Applies to every category below.
SPEC_SCHEMA: dict[str, list[tuple]] = {
    "_computing": [
        # Processor split into three atomic attributes (was "Intel / 3rd / i3").
        ("Processor Brand", "toggle", "", ["Intel", "AMD"]),
        ("Processor Series", "select", "", [
            "Core i3", "Core i5", "Core i7", "Core i9",
            "Ryzen 3", "Ryzen 5", "Ryzen 7", "Ryzen 9", "Xeon", "Other",
        ]),
        ("Processor Generation", "select", "", [
            "1st Gen", "2nd Gen", "3rd Gen", "4th Gen", "5th Gen", "6th Gen",
            "7th Gen", "8th Gen", "9th Gen", "10th Gen", "11th Gen", "12th Gen",
            "13th Gen", "14th Gen",
        ]),
        ("Cores", "number", "cores", []),
        ("RAM Size", "units", "", ["GB", "TB"]),
        ("RAM Type", "select", "", ["DDR3", "DDR4", "DDR5"]),
        ("Storage Size", "units", "", ["GB", "TB"]),
        ("Storage Type", "select", "", ["SSD", "HDD", "NVMe SSD"]),
        ("Display Size", "number", "inches", []),
        ("Operating System", "text", "", []),
        ("OS Licensed", "toggle", "", ["Yes", "No"]),
    ],
    "Monitor": [
        ("Screen Size", "number", "inch", []),
        ("Panel Type", "toggle", "", ["LED", "LCD"]),
        ("Resolution", "select", "", ["HD", "FHD", "QHD", "4K UHD", "5K", "8K UHD"]),
        ("Connectivity", "select", "", ["HDMI", "VGA", "DP", "HDMI+DP"]),
    ],
    "Printer": [
        ("Printer Type", "select", "", ["Laser", "InkJet"]),
        ("Colour Output", "select", "", ["BW", "BW+Color"]),
        ("Print Speed", "number", "PPM", []),
        ("Print Resolution", "select", "", ["300dpi", "600dpi", "1200dpi", "2400dpi"]),
        ("Duplex", "toggle", "", ["Yes", "No"]),
        ("Paper Size", "select", "", ["A4+Letter+Legal", "A3+A4+Letter+Legal"]),
        ("Connectivity", "select", "", ["USB", "USB+Ethernet", "USB+Ethernet+Wireless"]),
    ],
    "Scanner": [
        ("Scanner Type", "select", "", ["Flatbed", "Sheet-fed", "Duplex Scanner"]),
        ("Scan Resolution", "select", "", ["300dpi", "600dpi", "1200dpi", "2400dpi"]),
        ("Scan Speed", "number", "ppm", []),
        ("Paper Size", "select", "", ["A4+legal", "A3+A4+legal"]),
    ],
    "_copier": [
        ("Copier Type", "select", "", ["Digital", "Analog"]),
        ("Colour Output", "select", "", ["BW", "Color", "Color+BW"]),
        ("Copy Speed", "number", "PPM", []),
        ("Resolution", "select", "", ["300dpi", "600dpi", "1200dpi", "2400dpi"]),
        ("Duplex", "toggle", "", ["Yes", "No"]),
        ("Paper Size", "select", "", ["A4+Letter+Legal", "A3+A4+Letter+Legal"]),
        ("Connectivity", "select", "", ["USB", "USB+Ethernet", "USB+Ethernet+Wireless"]),
    ],
    "Access Point": [
        ("Frequency Bands", "toggle", "", ["Dual", "Single"]),
        ("Controller Based", "toggle", "", ["Yes", "No"]),
    ],
    "Switch": [
        ("Port Count", "select", "", ["8", "24", "48"]),
        ("Managed", "toggle", "", ["Yes", "No"]),
        ("VLAN Support", "toggle", "", ["Yes", "No"]),
    ],
    "UPS": [
        ("UPS Type", "toggle", "", ["Online", "Offline"]),
        ("Capacity", "units", "", ["VA", "KVA"]),
        ("Rack Mountable", "toggle", "", ["Yes", "No"]),
    ],
    "UTP Cable": [
        ("Category", "select", "", ["Cat5e", "Cat6", "Cat6A"]),
        ("Bandwidth", "number", "MHz", []),
        ("Max Speed", "select", "", ["1 Gbps", "10 Gbps"]),
    ],
    "IDF Rack": [
        ("Mount Type", "toggle", "", ["Floor Standing", "Wall Mount"]),
        ("Rack Size", "select", "", ["12U", "18U", "22U", "42U"]),
    ],
}

# Sub Assets that share the computing / copier schemas.
SCHEMA_ALIASES = {
    "CPU": "_computing",
    "Laptop": "_computing",
    "Desktop Set": "_computing",
    "Desktop Monitor": "Monitor",
    "Multifunction": "_copier",
    "Photocopier": "_copier",
}


def _yes(val) -> bool:
    return str(val).strip().upper() in ("Y", "YES", "TRUE", "1")


class Command(BaseCommand):
    help = "Seed the cascading catalogue (Main/Sub/Brand/Model + spec fields) from the Excel workbook."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="docs/Asset_Master_Data_Polished.xlsx",
            help="Path to the Asset Master Data workbook.",
        )

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl is required. Install it: pip install openpyxl")

        path = Path(opts["path"])
        if not path.exists():
            raise CommandError(f"Workbook not found: {path}")

        wb = openpyxl.load_workbook(path, data_only=True)
        counts = {"main": 0, "sub": 0, "brand": 0, "model": 0, "spec": 0}

        # ── Caches keyed by name (case-insensitive) ──────────────────────────
        cat_by_name: dict[str, AssetCategory] = {}
        type_by_key: dict[tuple[str, str], AssetType] = {}

        def get_category(name):
            key = name.strip().lower()
            if key not in cat_by_name:
                obj = AssetCategory.objects.filter(name__iexact=name.strip()).first()
                if obj is None:
                    obj = AssetCategory.objects.create(name=name.strip())
                    counts["main"] += 1
                cat_by_name[key] = obj
            return cat_by_name[key]

        def get_type(cat, name):
            key = (cat.pk, name.strip().lower())
            if key not in type_by_key:
                obj = AssetType.objects.filter(category=cat, name__iexact=name.strip()).first()
                if obj is None:
                    obj = AssetType.objects.create(category=cat, name=name.strip())
                    counts["sub"] += 1
                type_by_key[key] = obj
            return type_by_key[key]

        # ── 1. Main Asset ────────────────────────────────────────────────────
        for row in self._rows(wb, "1. Main Asset"):
            name = row.get("Main Asset Type")
            if name:
                cat = get_category(name)
                cat.is_active = _yes(row.get("Active", "Y"))
                cat.save(update_fields=["is_active", "updated_at"])

        # ── 2. Sub Asset ─────────────────────────────────────────────────────
        for row in self._rows(wb, "2. Sub Asset"):
            main, sub = row.get("Main Asset Type"), row.get("Sub Asset Type")
            if main and sub:
                t = get_type(get_category(main), sub)
                t.is_active = _yes(row.get("Active", "Y"))
                t.save(update_fields=["is_active", "updated_at"])

        # ── 3. Brand ─────────────────────────────────────────────────────────
        brand_cache: dict[tuple[int, str], CatalogBrand] = {}
        for row in self._rows(wb, "3. Brand"):
            main, sub, brand = row.get("Main Asset Type"), row.get("Sub Asset Type"), row.get("Brand")
            if not (main and sub and brand):
                continue
            t = get_type(get_category(main), sub)
            ckey = (t.pk, brand.strip().lower())
            obj = brand_cache.get(ckey) or CatalogBrand.objects.filter(sub_asset=t, name__iexact=brand.strip()).first()
            if obj is None:
                obj = CatalogBrand.objects.create(sub_asset=t, name=brand.strip())
                counts["brand"] += 1
            brand_cache[ckey] = obj

        # ── 4. Model ─────────────────────────────────────────────────────────
        for row in self._rows(wb, "4. Model"):
            main, sub, brand, model = (
                row.get("Main Asset Type"), row.get("Sub Asset Type"),
                row.get("Brand"), row.get("Model"),
            )
            if not (main and sub and brand and model):
                continue
            t = get_type(get_category(main), sub)
            b = brand_cache.get((t.pk, brand.strip().lower())) or CatalogBrand.objects.filter(
                sub_asset=t, name__iexact=brand.strip()
            ).first()
            if b is None:
                b = CatalogBrand.objects.create(sub_asset=t, name=brand.strip())
                counts["brand"] += 1
                brand_cache[(t.pk, brand.strip().lower())] = b
            if not CatalogModel.objects.filter(brand=b, name__iexact=str(model).strip()).exists():
                CatalogModel.objects.create(brand=b, name=str(model).strip())
                counts["model"] += 1

        # ── 5. Spec fields per Sub Asset ─────────────────────────────────────
        for (cat_pk, _), t in type_by_key.items():
            schema_key = SCHEMA_ALIASES.get(t.name, t.name)
            schema = SPEC_SCHEMA.get(schema_key)
            if not schema:
                continue
            for order, (label, widget, unit, options) in enumerate(schema):
                key = slugify_key(label)
                _, created = SubAssetSpecField.objects.get_or_create(
                    sub_asset=t, key=key,
                    defaults={
                        "label": label, "widget": widget, "unit": unit,
                        "options": options, "order": order,
                    },
                )
                if created:
                    counts["spec"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded catalogue — new rows: {counts['main']} Main, {counts['sub']} Sub, "
            f"{counts['brand']} Brand, {counts['model']} Model, {counts['spec']} Spec fields."
        ))

    @staticmethod
    def _rows(wb, sheet_name):
        """Yield each data row of a sheet as a {header: value} dict."""
        ws = wb[sheet_name]
        rows = ws.iter_rows(values_only=True)
        headers = [str(h).strip() if h is not None else "" for h in next(rows)]
        for raw in rows:
            if not any(c is not None for c in raw):
                continue
            yield {headers[i]: raw[i] for i in range(len(headers)) if i < len(raw)}
