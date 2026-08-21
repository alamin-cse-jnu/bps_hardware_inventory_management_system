import io

import openpyxl
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from locations.models import Building, Level, Location

from .models import (
    AssetCategory,
    AssetComponent,
    AssetItem,
    AssetType,
    is_placeholder_serial,
)
from .services.excel_import import (
    FIXED_COLUMNS,
    ExcelImportExecutor,
    ExcelImportValidator,
    ExcelTemplateGenerator,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_category(name="Computing") -> AssetCategory:
    return AssetCategory.objects.create(name=name)


def make_type(category=None, name="LAPTOP", has_components=False) -> AssetType:
    if category is None:
        category = make_category()
    return AssetType.objects.create(
        category=category,
        name=name,
        has_components=has_components,
        spec_schema=["cpu", "ram"] if has_components else ["cpu"],
    )


def make_item(asset_type=None, asset_tag="PC-2024-0001", status=AssetItem.Status.IN_STOCK) -> AssetItem:
    if asset_type is None:
        asset_type = make_type()
    return AssetItem.objects.create(
        asset_tag=asset_tag,
        asset_type=asset_type,
        brand="Dell",
        model_name="Latitude 5540",
        status=status,
    )


# ---------------------------------------------------------------------------
# State machine — valid transitions
# ---------------------------------------------------------------------------

class ValidTransitionTests(TestCase):
    """Every transition listed in CLAUDE.md must succeed."""

    def _item(self, status):
        return make_item(status=status, asset_tag=f"TAG-{status}")

    def test_in_stock_to_assigned(self):
        item = self._item(AssetItem.Status.IN_STOCK)
        item.change_status(AssetItem.Status.ASSIGNED)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.ASSIGNED)

    def test_in_stock_to_maintenance(self):
        item = self._item(AssetItem.Status.IN_STOCK)
        item.change_status(AssetItem.Status.MAINTENANCE)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.MAINTENANCE)

    def test_in_stock_to_disposed(self):
        item = self._item(AssetItem.Status.IN_STOCK)
        item.change_status(AssetItem.Status.DISPOSED)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.DISPOSED)

    def test_assigned_to_in_stock(self):
        item = self._item(AssetItem.Status.ASSIGNED)
        item.change_status(AssetItem.Status.IN_STOCK)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.IN_STOCK)

    def test_assigned_to_maintenance(self):
        item = self._item(AssetItem.Status.ASSIGNED)
        item.change_status(AssetItem.Status.MAINTENANCE)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.MAINTENANCE)

    def test_assigned_to_lost(self):
        item = self._item(AssetItem.Status.ASSIGNED)
        item.change_status(AssetItem.Status.LOST)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.LOST)

    def test_assigned_to_damaged(self):
        item = self._item(AssetItem.Status.ASSIGNED)
        item.change_status(AssetItem.Status.DAMAGED)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.DAMAGED)

    def test_assigned_to_disposed(self):
        item = self._item(AssetItem.Status.ASSIGNED)
        item.change_status(AssetItem.Status.DISPOSED)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.DISPOSED)

    def test_maintenance_to_in_stock(self):
        item = self._item(AssetItem.Status.MAINTENANCE)
        item.change_status(AssetItem.Status.IN_STOCK)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.IN_STOCK)

    def test_maintenance_to_disposed(self):
        item = self._item(AssetItem.Status.MAINTENANCE)
        item.change_status(AssetItem.Status.DISPOSED)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.DISPOSED)

    def test_lost_to_in_stock(self):
        item = self._item(AssetItem.Status.LOST)
        item.change_status(AssetItem.Status.IN_STOCK)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.IN_STOCK)

    def test_lost_to_disposed(self):
        item = self._item(AssetItem.Status.LOST)
        item.change_status(AssetItem.Status.DISPOSED)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.DISPOSED)

    def test_damaged_to_in_stock(self):
        item = self._item(AssetItem.Status.DAMAGED)
        item.change_status(AssetItem.Status.IN_STOCK)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.IN_STOCK)

    def test_damaged_to_maintenance(self):
        item = self._item(AssetItem.Status.DAMAGED)
        item.change_status(AssetItem.Status.MAINTENANCE)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.MAINTENANCE)

    def test_damaged_to_disposed(self):
        item = self._item(AssetItem.Status.DAMAGED)
        item.change_status(AssetItem.Status.DISPOSED)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetItem.Status.DISPOSED)


# ---------------------------------------------------------------------------
# State machine — invalid transitions
# ---------------------------------------------------------------------------

class InvalidTransitionTests(TestCase):
    """Transitions not in CLAUDE.md must raise ValidationError."""

    def _assert_invalid(self, from_status, to_status):
        item = make_item(
            status=from_status,
            asset_tag=f"TAG-{from_status}-{to_status}",
        )
        with self.assertRaises(ValidationError):
            item.change_status(to_status)

    def test_in_stock_cannot_go_to_lost(self):
        self._assert_invalid(AssetItem.Status.IN_STOCK, AssetItem.Status.LOST)

    def test_in_stock_cannot_go_to_damaged(self):
        self._assert_invalid(AssetItem.Status.IN_STOCK, AssetItem.Status.DAMAGED)

    def test_maintenance_cannot_go_to_assigned(self):
        self._assert_invalid(AssetItem.Status.MAINTENANCE, AssetItem.Status.ASSIGNED)

    def test_maintenance_cannot_go_to_lost(self):
        self._assert_invalid(AssetItem.Status.MAINTENANCE, AssetItem.Status.LOST)

    def test_maintenance_cannot_go_to_damaged(self):
        self._assert_invalid(AssetItem.Status.MAINTENANCE, AssetItem.Status.DAMAGED)

    def test_lost_cannot_go_to_assigned(self):
        self._assert_invalid(AssetItem.Status.LOST, AssetItem.Status.ASSIGNED)

    def test_lost_cannot_go_to_maintenance(self):
        self._assert_invalid(AssetItem.Status.LOST, AssetItem.Status.MAINTENANCE)

    def test_lost_cannot_go_to_damaged(self):
        self._assert_invalid(AssetItem.Status.LOST, AssetItem.Status.DAMAGED)

    def test_disposed_cannot_go_to_in_stock(self):
        self._assert_invalid(AssetItem.Status.DISPOSED, AssetItem.Status.IN_STOCK)

    def test_disposed_cannot_go_to_assigned(self):
        self._assert_invalid(AssetItem.Status.DISPOSED, AssetItem.Status.ASSIGNED)

    def test_disposed_cannot_go_to_maintenance(self):
        self._assert_invalid(AssetItem.Status.DISPOSED, AssetItem.Status.MAINTENANCE)

    def test_disposed_cannot_go_to_lost(self):
        self._assert_invalid(AssetItem.Status.DISPOSED, AssetItem.Status.LOST)

    def test_disposed_cannot_go_to_damaged(self):
        self._assert_invalid(AssetItem.Status.DISPOSED, AssetItem.Status.DAMAGED)


# ---------------------------------------------------------------------------
# AssetComponent validation
# ---------------------------------------------------------------------------

class AssetComponentValidationTests(TestCase):
    def setUp(self):
        cat = make_category()
        self.pc_type = make_type(cat, "PC_SET", has_components=True)
        self.laptop_type = make_type(cat, "LAPTOP", has_components=False)
        self.pc = make_item(self.pc_type, "PC-001")
        self.laptop = make_item(self.laptop_type, "LT-001")

    def test_component_allowed_on_pc_set(self):
        comp = AssetComponent(
            parent_asset=self.pc,
            component_type=AssetComponent.ComponentType.MONITOR,
            brand="Samsung",
        )
        comp.full_clean()  # must not raise
        comp.save()
        self.assertEqual(comp.parent_asset, self.pc)

    def test_component_rejected_on_non_component_type(self):
        comp = AssetComponent(
            parent_asset=self.laptop,
            component_type=AssetComponent.ComponentType.RAM,
        )
        with self.assertRaises(ValidationError) as ctx:
            comp.full_clean()
        self.assertIn("parent_asset", ctx.exception.message_dict)

    def test_removed_component_kept_in_db(self):
        """Removed components stay in DB with is_active=False (architectural decision #1)."""
        comp = AssetComponent.objects.create(
            parent_asset=self.pc,
            component_type=AssetComponent.ComponentType.RAM,
            is_active=True,
        )
        comp.is_active = False
        comp.removed_at = timezone.now()
        comp.removal_reason = "Upgraded to 16GB"
        comp.save()

        self.assertIsNotNone(AssetComponent.objects.filter(pk=comp.pk).first())
        self.assertFalse(AssetComponent.objects.get(pk=comp.pk).is_active)


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------

class SoftDeleteTests(TestCase):
    def test_soft_delete_sets_flags(self):
        item = make_item(asset_tag="TAG-SOFT-DEL")
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)

        item.soft_delete()
        item.refresh_from_db()

        self.assertTrue(item.is_deleted)
        self.assertIsNotNone(item.deleted_at)

    def test_soft_delete_does_not_remove_row(self):
        item = make_item(asset_tag="TAG-SOFT-KEEP")
        pk = item.pk
        item.soft_delete()
        self.assertTrue(AssetItem.objects.filter(pk=pk).exists())


# ---------------------------------------------------------------------------
# asset_tag uniqueness
# ---------------------------------------------------------------------------

class AssetTagUniquenessTests(TestCase):
    def test_duplicate_asset_tag_raises_integrity_error(self):
        make_item(asset_tag="UNIQUE-001")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            # Bypass full_clean to hit the DB constraint directly
            AssetItem.objects.create(
                asset_tag="UNIQUE-001",
                asset_type=make_type(make_category("Networking"), "SWITCH"),
                brand="Cisco",
                model_name="SG350",
            )


# ---------------------------------------------------------------------------
# is_assignable property
# ---------------------------------------------------------------------------

class IsAssignableTests(TestCase):
    def test_in_stock_not_deleted_is_assignable(self):
        item = make_item(status=AssetItem.Status.IN_STOCK)
        self.assertTrue(item.is_assignable)

    def test_assigned_is_not_assignable(self):
        item = make_item(status=AssetItem.Status.ASSIGNED, asset_tag="TAG-ASGN")
        self.assertFalse(item.is_assignable)

    def test_in_stock_but_deleted_is_not_assignable(self):
        item = make_item(status=AssetItem.Status.IN_STOCK, asset_tag="TAG-DEL")
        item.soft_delete()
        self.assertFalse(item.is_assignable)


# ===========================================================================
# Excel Import Tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared fixtures for import tests
# ---------------------------------------------------------------------------

def make_import_category() -> AssetCategory:
    return AssetCategory.objects.create(name="ImportCat")


def make_import_type(spec_schema=None) -> AssetType:
    if spec_schema is None:
        spec_schema = ["cpu", "ram"]
    cat = make_import_category()
    return AssetType.objects.create(
        category=cat,
        name="LAPTOP",
        spec_schema=spec_schema,
    )


def make_location_hierarchy():
    """Three distinct flat locations (each with a unique full_path)."""
    b = Building.objects.create(name="Parliament Bhaban")
    lvl = Level.objects.create(name="Level-3")
    building = Location.objects.create(name="Reception", building=b)
    floor = Location.objects.create(name="Corridor", building=b, level=lvl)
    room = Location.objects.create(name="NOC Room", building=b, level=lvl, room="301")
    return building, floor, room


def make_excel_file(headers: list, rows: list) -> io.BytesIO:
    """Build a minimal .xlsx with a 'Data Entry' sheet."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data Entry"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _base_headers(asset_type: AssetType) -> list:
    spec_cols = [f"spec_{k}" for k in (asset_type.spec_schema or [])]
    return FIXED_COLUMNS + spec_cols


def _valid_row_values(location_path: str = "") -> list:
    """Values matching the FIXED_COLUMNS order + 2 spec cols (cpu, ram)."""
    return [
        "",               # asset_tag (blank → auto-generate)
        "SN-TEST-001",    # serial_number
        "Dell",           # brand
        "Latitude 5540",  # model_name
        "2024-01-15",     # purchase_date
        "PO-001",         # purchase_order
        "Tech Supply",    # supplier
        "45000.00",       # purchase_cost
        "2027-01-15",     # warranty_expiry
        "2025-01-15",     # amc_expiry
        location_path,    # storage_location_path
        "Test notes",     # notes
        "Intel i7",       # spec_cpu
        "16GB",           # spec_ram
    ]


def make_import_user():
    return User.objects.create_user(username="importer", password="pass")


# ---------------------------------------------------------------------------
# ExcelTemplateGenerator tests
# ---------------------------------------------------------------------------

class ExcelTemplateGeneratorTests(TestCase):
    def setUp(self):
        self.asset_type = make_import_type(spec_schema=["cpu", "ram", "storage"])

    def test_template_has_three_sheets(self):
        wb = ExcelTemplateGenerator().generate_template(self.asset_type.pk)
        self.assertEqual(wb.sheetnames, ["Data Entry", "Instructions", "Valid Locations"])

    def test_template_fixed_columns_in_data_entry(self):
        wb = ExcelTemplateGenerator().generate_template(self.asset_type.pk)
        ws = wb["Data Entry"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1) if ws.cell(1, c).value]
        for col in FIXED_COLUMNS:
            self.assertIn(col, headers, f"Missing fixed column: {col}")

    def test_template_dynamic_spec_columns(self):
        wb = ExcelTemplateGenerator().generate_template(self.asset_type.pk)
        ws = wb["Data Entry"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1) if ws.cell(1, c).value]
        for spec_key in self.asset_type.spec_schema:
            self.assertIn(f"spec_{spec_key}", headers, f"Missing spec column: spec_{spec_key}")

    def test_template_has_example_row(self):
        wb = ExcelTemplateGenerator().generate_template(self.asset_type.pk)
        ws = wb["Data Entry"]
        # Row 2 should have at least brand filled in
        row2_vals = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]
        non_empty = [v for v in row2_vals if v]
        self.assertGreater(len(non_empty), 0, "Example row is completely empty")

    def test_template_valid_locations_sheet_lists_active_locations(self):
        building, floor, room = make_location_hierarchy()
        wb = ExcelTemplateGenerator().generate_template(self.asset_type.pk)
        ws = wb["Valid Locations"]
        paths = [ws.cell(r, 1).value for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value]
        self.assertIn(building.full_path, paths)
        self.assertIn(floor.full_path, paths)
        self.assertIn(room.full_path, paths)


# ---------------------------------------------------------------------------
# ExcelImportValidator tests
# ---------------------------------------------------------------------------

class ExcelImportValidatorTests(TestCase):
    def setUp(self):
        self.asset_type = make_import_type(spec_schema=["cpu", "ram"])
        self.building, self.floor, self.room = make_location_hierarchy()
        self.headers = _base_headers(self.asset_type)

    def _validate(self, rows):
        f = make_excel_file(self.headers, rows)
        return ExcelImportValidator().validate(f, self.asset_type.pk)

    def test_valid_row_passes(self):
        results = self._validate([_valid_row_values(self.room.full_path)])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "valid")
        self.assertEqual(results[0]["errors"], [])

    def test_missing_brand_fails(self):
        row = _valid_row_values()
        row[2] = ""  # brand is index 2
        results = self._validate([row])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(any("brand" in e for e in results[0]["errors"]))

    def test_missing_model_fails(self):
        row = _valid_row_values()
        row[3] = ""  # model_name is index 3
        results = self._validate([row])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(any("model_name" in e for e in results[0]["errors"]))

    def test_blank_serial_produces_warning(self):
        row = _valid_row_values()
        row[1] = ""  # serial_number is index 1
        results = self._validate([row])
        self.assertIn(results[0]["status"], ("warning",))
        self.assertTrue(any("serial_number" in w for w in results[0]["warnings"]))

    def test_duplicate_asset_tag_fails(self):
        # Pre-create an asset with tag "TAG-DUP-001"
        make_item(asset_type=self.asset_type, asset_tag="TAG-DUP-001")
        row = _valid_row_values()
        row[0] = "TAG-DUP-001"  # asset_tag
        results = self._validate([row])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(any("TAG-DUP-001" in e for e in results[0]["errors"]))

    def test_invalid_location_path_fails(self):
        row = _valid_row_values("Completely → Wrong → Path")
        results = self._validate([row])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(any("not found" in e.lower() for e in results[0]["errors"]))

    def test_valid_location_path_resolves(self):
        row = _valid_row_values(self.room.full_path)
        results = self._validate([row])
        self.assertEqual(results[0]["data"]["storage_location_id"], self.room.pk)

    def test_empty_rows_are_skipped(self):
        # Mix: one valid row, two empty rows
        valid = _valid_row_values()
        results = self._validate([valid, ["", "", "", "", "", "", "", "", "", "", "", "", "", ""], [None] * 14])
        self.assertEqual(len(results), 1)

    def test_invalid_date_format_fails(self):
        row = _valid_row_values()
        row[4] = "15/01/2024"  # purchase_date — wrong format
        results = self._validate([row])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(any("date" in e.lower() for e in results[0]["errors"]))

    def test_invalid_cost_fails(self):
        row = _valid_row_values()
        row[7] = "not-a-number"  # purchase_cost
        results = self._validate([row])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(any("decimal" in e.lower() for e in results[0]["errors"]))


# ---------------------------------------------------------------------------
# ExcelImportExecutor tests
# ---------------------------------------------------------------------------

class ExcelImportExecutorTests(TestCase):
    def setUp(self):
        self.asset_type = make_import_type(spec_schema=["cpu", "ram"])
        self.user = make_import_user()

    def _valid_row_dict(self, asset_tag="", serial="SN-001", brand="Dell", model="D1", row_num=2):
        return {
            "row": row_num,
            "status": "valid",
            "errors": [],
            "warnings": [],
            "data": {
                "asset_tag": asset_tag,
                "serial_number": serial,
                "brand": brand,
                "model_name": model,
                "purchase_date": None,
                "purchase_order": "",
                "supplier": "",
                "purchase_cost": None,
                "warranty_expiry": None,
                "amc_expiry": None,
                "storage_location_id": None,
                "notes": "",
                "specifications": {"cpu": "i7", "ram": "16GB"},
            },
        }

    def test_creates_assets_from_valid_rows(self):
        rows = [self._valid_row_dict(asset_tag="LAP-2024-TEST1")]
        result = ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["errors"], [])
        self.assertTrue(AssetItem.objects.filter(asset_tag="LAP-2024-TEST1").exists())

    def test_auto_generates_asset_tag_format(self):
        rows = [self._valid_row_dict()]  # asset_tag blank
        result = ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        self.assertEqual(result["created"], 1)
        item = AssetItem.objects.first()
        year = timezone.now().year
        self.assertRegex(item.asset_tag, rf"^LAP-{year}-\d{{4}}$")

    def test_asset_tag_sequence_increments_within_batch(self):
        rows = [
            self._valid_row_dict(row_num=2, serial="SN-A"),
            self._valid_row_dict(row_num=3, serial="SN-B"),
        ]
        result = ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        self.assertEqual(result["created"], 2)
        year = timezone.now().year
        tags = sorted(AssetItem.objects.values_list("asset_tag", flat=True))
        self.assertEqual(tags[0], f"LAP-{year}-0001")
        self.assertEqual(tags[1], f"LAP-{year}-0002")

    def test_asset_tag_sequence_continues_from_db(self):
        # Pre-existing asset with sequence 0005
        year = timezone.now().year
        make_item(asset_type=self.asset_type, asset_tag=f"LAP-{year}-0005")
        rows = [self._valid_row_dict()]
        ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        self.assertTrue(AssetItem.objects.filter(asset_tag=f"LAP-{year}-0006").exists())

    def test_sets_created_by_user(self):
        rows = [self._valid_row_dict(asset_tag="LAP-USR-001")]
        ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        item = AssetItem.objects.get(asset_tag="LAP-USR-001")
        self.assertEqual(item.created_by, self.user)

    def test_status_set_to_in_stock(self):
        rows = [self._valid_row_dict(asset_tag="LAP-STOCK-001")]
        ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        item = AssetItem.objects.get(asset_tag="LAP-STOCK-001")
        self.assertEqual(item.status, AssetItem.Status.IN_STOCK)

    def test_skips_error_rows(self):
        rows = [
            self._valid_row_dict(asset_tag="LAP-OK-001"),
            {**self._valid_row_dict(asset_tag="LAP-BAD-001", row_num=3), "status": "error"},
        ]
        result = ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertFalse(AssetItem.objects.filter(asset_tag="LAP-BAD-001").exists())

    def test_transaction_rollback_on_duplicate_tag_within_batch(self):
        """Two rows with the same explicit tag: first succeeds, second fails → rollback both."""
        rows = [
            self._valid_row_dict(asset_tag="LAP-DUP-001", row_num=2),
            self._valid_row_dict(asset_tag="LAP-DUP-001", row_num=3),  # duplicate
        ]
        result = ExcelImportExecutor().execute(rows, self.asset_type.pk, self.user)
        self.assertEqual(result["created"], 0)
        self.assertFalse(AssetItem.objects.filter(asset_tag="LAP-DUP-001").exists())
        self.assertGreater(len(result["errors"]), 0)

    def test_warning_rows_are_imported(self):
        row = {**self._valid_row_dict(asset_tag="LAP-WARN-001"), "status": "warning"}
        result = ExcelImportExecutor().execute([row], self.asset_type.pk, self.user)
        self.assertEqual(result["created"], 1)
        self.assertTrue(AssetItem.objects.filter(asset_tag="LAP-WARN-001").exists())


# ---------------------------------------------------------------------------
# Catalog management (in-app asset type / category config)
# ---------------------------------------------------------------------------

from django.contrib.auth.models import Group  # noqa: E402

from .specs import compose_schema, slugify_spec_key, split_schema  # noqa: E402


def _role_user(username, group):
    u = User.objects.create_user(username=username, password="pw12345!")
    grp, _ = Group.objects.get_or_create(name=group)
    u.groups.add(grp)
    return u


class SpecSchemaHelperTests(TestCase):
    def test_slugify(self):
        self.assertEqual(slugify_spec_key("WiFi Standard"), "wifi_standard")
        self.assertEqual(slugify_spec_key("  Ports!! "), "ports")

    def test_compose_orders_known_then_custom_and_dedupes(self):
        # known fields come back in registry order regardless of input order;
        # custom 'ram' is dropped (collides with known), 'bogus' known ignored.
        schema = compose_schema(["ram", "cpu", "bogus"], ["Ports", "WiFi Standard", "ram"])
        self.assertEqual(schema, ["cpu", "ram", "ports", "wifi_standard"])

    def test_split_schema(self):
        known, custom = split_schema(["cpu", "ports", "ram"])
        self.assertEqual(known, ["cpu", "ram"])
        self.assertEqual(custom, ["ports"])


class CatalogPermissionTests(TestCase):
    def setUp(self):
        self.category = make_category()

    def test_it_officer_forbidden(self):
        self.client.force_login(_role_user("officer", "IT Officer"))
        self.assertEqual(self.client.get("/catalog/").status_code, 403)

    def test_viewer_forbidden(self):
        self.client.force_login(_role_user("viewer", "Viewer"))
        self.assertEqual(self.client.get("/catalog/").status_code, 403)

    def test_admin_allowed(self):
        self.client.force_login(_role_user("admin", "Admin"))
        self.assertEqual(self.client.get("/catalog/").status_code, 200)


class CatalogTypeViewTests(TestCase):
    def setUp(self):
        self.admin = _role_user("admin", "Admin")
        self.client.force_login(self.admin)
        self.category = make_category("Computing Equipment")

    def test_create_type_with_mixed_schema(self):
        resp = self.client.post("/catalog/types/new/", {
            "name": "Router",
            "category": self.category.pk,
            "known_specs": ["cpu", "ram"],
            "custom_specs": ["Ports", "WiFi Standard"],
            "is_active": "on",
        })
        self.assertRedirects(resp, "/catalog/")
        t = AssetType.objects.get(name="Router")
        self.assertEqual(t.spec_schema, ["cpu", "ram", "ports", "wifi_standard"])
        self.assertTrue(t.is_active)
        self.assertFalse(t.has_components)

    def test_duplicate_name_in_category_rejected(self):
        make_type(category=self.category, name="Laptop")
        resp = self.client.post("/catalog/types/new/", {
            "name": "laptop",  # case-insensitive clash
            "category": self.category.pk,
        })
        self.assertEqual(resp.status_code, 200)  # re-renders form
        self.assertContains(resp, "already exists")
        self.assertEqual(AssetType.objects.filter(name__iexact="laptop").count(), 1)

    def test_edit_preserves_and_updates_schema(self):
        t = make_type(category=self.category, name="PC Set", has_components=True)
        resp = self.client.post(f"/catalog/types/{t.pk}/edit/", {
            "name": "PC Set",
            "category": self.category.pk,
            "known_specs": ["cpu", "ram", "storage"],
            "has_components": "on",
            "is_active": "on",
        })
        self.assertRedirects(resp, "/catalog/")
        t.refresh_from_db()
        self.assertEqual(t.spec_schema, ["cpu", "ram", "storage"])

    def test_toggle_active(self):
        t = make_type(category=self.category, name="Scanner")
        self.client.post(f"/catalog/types/{t.pk}/toggle/")
        t.refresh_from_db()
        self.assertFalse(t.is_active)

    def test_delete_blocked_when_items_exist(self):
        t = make_type(category=self.category, name="UPS")
        make_item(asset_type=t, asset_tag="UPS-1")
        resp = self.client.post(f"/catalog/types/{t.pk}/delete/", follow=True)
        self.assertTrue(AssetType.objects.filter(pk=t.pk).exists())
        self.assertContains(resp, "Cannot delete")

    def test_delete_allowed_when_empty(self):
        t = make_type(category=self.category, name="Projector")
        self.client.post(f"/catalog/types/{t.pk}/delete/")
        self.assertFalse(AssetType.objects.filter(pk=t.pk).exists())


class CatalogCategoryViewTests(TestCase):
    def setUp(self):
        self.client.force_login(_role_user("admin", "Admin"))

    def test_create_category(self):
        resp = self.client.post("/catalog/categories/new/", {
            "name": "Networking", "is_active": "on",
        })
        self.assertRedirects(resp, "/catalog/")
        self.assertTrue(AssetCategory.objects.filter(name="Networking").exists())

    def test_delete_blocked_when_types_exist(self):
        cat = make_category("HasTypes")
        make_type(category=cat, name="Switch")
        resp = self.client.post(f"/catalog/categories/{cat.pk}/delete/", follow=True)
        self.assertTrue(AssetCategory.objects.filter(pk=cat.pk).exists())
        self.assertContains(resp, "Cannot delete")


# ---------------------------------------------------------------------------
# Bulk Add batches — history, re-apply on edit, cascade soft-delete
# ---------------------------------------------------------------------------

from catalogue.models import SubAssetSpecField  # noqa: E402

from .models import AssetBatch  # noqa: E402


class BulkBatchTests(TestCase):
    def setUp(self):
        self.officer = _role_user("officer", "IT Officer")
        self.client.force_login(self.officer)
        self.category = make_category("Computing")
        self.atype = make_type(category=self.category, name="Laptop")
        # A single text spec field so specs flow through collect_values.
        SubAssetSpecField.objects.create(
            sub_asset=self.atype, key="cpu", label="CPU", widget="text",
        )

    def _bulk_post(self, quantity=3, serials=None, **overrides):
        serials = serials or [f"SN-{i:03d}" for i in range(1, quantity + 1)]
        data = {
            "asset_type": self.atype.pk,
            "brand": "Dell",
            "model_name": "Latitude 5540",
            "quantity": str(quantity),
            "serial_numbers": "\n".join(serials),
            "spec_cpu": "i5",
            "notes": "batch one",
        }
        data.update(overrides)
        return self.client.post("/bulk-add/", data)

    def test_bulk_add_creates_one_batch_linking_all_assets(self):
        resp = self._bulk_post(quantity=3)
        self.assertEqual(AssetBatch.objects.count(), 1)
        batch = AssetBatch.objects.get()
        self.assertRedirects(resp, f"/batches/{batch.pk}/")
        self.assertEqual(batch.quantity, 3)
        self.assertEqual(batch.assets.count(), 3)
        self.assertEqual(batch.reference[:3], "BA-")
        # Every created asset points back to the batch.
        for a in batch.assets.all():
            self.assertEqual(a.batch_id, batch.pk)
            self.assertEqual(a.specifications.get("cpu"), "i5")

    def test_five_bulk_adds_show_five_history_rows(self):
        for batch_no in range(5):
            # Serials are unique per batch — the same plate cannot be added twice.
            self._bulk_post(quantity=2, serials=[f"SN-B{batch_no}-{i}" for i in range(2)])
        self.assertEqual(AssetBatch.objects.count(), 5)
        resp = self.client.get("/batches/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["batch_rows"]), 5)

    def test_bulk_add_records_create_audit_entry(self):
        self._bulk_post(quantity=2)
        from audit.models import AuditLog
        batch = AssetBatch.objects.get()
        self.assertTrue(
            AuditLog.objects.filter(
                target_model="assets.AssetBatch",
                target_id=str(batch.pk),
                action="CREATE",
            ).exists()
        )

    def test_edit_reapplies_shared_values_to_all_assets(self):
        self._bulk_post(quantity=4)
        batch = AssetBatch.objects.get()
        resp = self.client.post(f"/batches/{batch.pk}/edit/", {
            "asset_type": self.atype.pk,
            "brand": "HP",
            "model_name": "EliteBook 840",
            "spec_cpu": "i7",
            "notes": "corrected",
            "purchase_order": "PO/2026/9",
        })
        self.assertRedirects(resp, f"/batches/{batch.pk}/")
        batch.refresh_from_db()
        self.assertEqual(batch.brand, "HP")
        # All member assets updated to the new shared values.
        for a in batch.assets.all():
            self.assertEqual(a.brand, "HP")
            self.assertEqual(a.model_name, "EliteBook 840")
            self.assertEqual(a.specifications.get("cpu"), "i7")
            self.assertEqual(a.purchase_order, "PO/2026/9")

    def test_edit_updates_assigned_asset_values_but_keeps_status(self):
        self._bulk_post(quantity=2)
        batch = AssetBatch.objects.get()
        asset = batch.assets.first()
        asset.status = AssetItem.Status.ASSIGNED
        asset.save(update_fields=["status"])

        self.client.post(f"/batches/{batch.pk}/edit/", {
            "asset_type": self.atype.pk,
            "brand": "Lenovo",
            "model_name": "ThinkPad",
            "spec_cpu": "i9",
        })
        asset.refresh_from_db()
        # Shared value changed…
        self.assertEqual(asset.brand, "Lenovo")
        # …but status/serial/tag are untouched.
        self.assertEqual(asset.status, AssetItem.Status.ASSIGNED)

    def test_edit_records_update_audit_with_changes(self):
        self._bulk_post(quantity=2)
        batch = AssetBatch.objects.get()
        self.client.post(f"/batches/{batch.pk}/edit/", {
            "asset_type": self.atype.pk,
            "brand": "Acer",
            "model_name": "Latitude 5540",
            "spec_cpu": "i5",
        })
        from audit.models import AuditLog
        log = AuditLog.objects.filter(
            target_model="assets.AssetBatch", action="UPDATE",
        ).latest("created_at")
        self.assertIn("brand", log.changes)
        self.assertEqual(log.changes["brand"], ["Dell", "Acer"])

    def test_delete_soft_deletes_batch_and_assets(self):
        self._bulk_post(quantity=3)
        batch = AssetBatch.objects.get()
        resp = self.client.post(f"/batches/{batch.pk}/delete/")
        self.assertRedirects(resp, "/batches/")
        batch.refresh_from_db()
        self.assertTrue(batch.is_deleted)
        self.assertEqual(batch.assets.filter(is_deleted=False).count(), 0)
        self.assertEqual(batch.assets.filter(is_deleted=True).count(), 3)
        # Deleted batch drops out of the history list.
        self.assertNotContains(self.client.get("/batches/"), batch.reference)

    def test_viewer_cannot_edit_or_delete(self):
        self._bulk_post(quantity=1)
        batch = AssetBatch.objects.get()
        self.client.force_login(_role_user("viewer", "Viewer"))
        self.assertEqual(self.client.get(f"/batches/{batch.pk}/edit/").status_code, 403)
        self.assertEqual(self.client.get(f"/batches/{batch.pk}/delete/").status_code, 403)
        # …but can still view history and detail.
        self.assertEqual(self.client.get("/batches/").status_code, 200)
        self.assertEqual(self.client.get(f"/batches/{batch.pk}/").status_code, 200)


# ---------------------------------------------------------------------------
# Serial number uniqueness
# ---------------------------------------------------------------------------

class SerialNumberUniquenessTests(TestCase):
    """Model + DB level: one serial number, at most one live asset."""

    def setUp(self):
        self.atype = make_type()

    def _item(self, tag, serial, **kwargs):
        return AssetItem.objects.create(
            asset_tag=tag,
            asset_type=self.atype,
            brand="Dell",
            model_name="Latitude 5540",
            serial_number=serial,
            **kwargs,
        )

    def test_duplicate_serial_raises_integrity_error(self):
        from django.db import IntegrityError
        self._item("SER-001", "SN-DUP-1")
        with self.assertRaises(IntegrityError):
            self._item("SER-002", "SN-DUP-1")

    def test_duplicate_serial_is_case_insensitive(self):
        from django.db import IntegrityError
        self._item("SER-001", "sn-dup-1")
        with self.assertRaises(IntegrityError):
            self._item("SER-002", "SN-DUP-1")

    def test_blank_serials_may_repeat(self):
        self._item("SER-001", "")
        self._item("SER-002", "")
        self.assertEqual(AssetItem.objects.filter(serial_number="").count(), 2)

    def test_serial_freed_by_soft_delete(self):
        first = self._item("SER-001", "SN-REUSE")
        first.soft_delete()
        # The same serial can now be entered again on a live asset.
        self._item("SER-002", "SN-REUSE")
        self.assertEqual(
            AssetItem.objects.filter(serial_number="SN-REUSE", is_deleted=False).count(), 1
        )

    def test_clean_reports_duplicate_with_conflicting_tag(self):
        self._item("SER-001", "SN-CLEAN")
        dup = AssetItem(
            asset_tag="SER-002", asset_type=self.atype,
            brand="Dell", model_name="Latitude 5540", serial_number="SN-CLEAN",
        )
        with self.assertRaises(ValidationError) as ctx:
            dup.full_clean()
        message = str(ctx.exception.message_dict["serial_number"])
        self.assertIn("SER-001", message)
        self.assertIn("must be unique", message)

    def test_clean_allows_asset_to_keep_its_own_serial(self):
        asset = self._item("SER-001", "SN-SELF")
        asset.notes = "unchanged serial"
        asset.full_clean()  # must not raise

    def test_serial_conflict_ignores_deleted_and_blank(self):
        deleted = self._item("SER-001", "SN-GONE")
        deleted.soft_delete()
        self.assertIsNone(AssetItem.serial_conflict("SN-GONE"))
        self.assertIsNone(AssetItem.serial_conflict(""))
        self.assertIsNone(AssetItem.serial_conflict("   "))

    def test_serial_conflict_matches_ignoring_case_and_padding(self):
        live = self._item("SER-001", "SN-MATCH")
        self.assertEqual(AssetItem.serial_conflict("  sn-match "), live)


class SerialNumberFormValidationTests(TestCase):
    """The add/edit/bulk forms reject duplicates with a message, not a 500."""

    def setUp(self):
        self.officer = _role_user("serial-officer", "IT Officer")
        self.client.force_login(self.officer)
        self.category = make_category("Computing")
        self.atype = make_type(category=self.category, name="Laptop")
        SubAssetSpecField.objects.create(
            sub_asset=self.atype, key="cpu", label="CPU", widget="text",
        )
        self.existing = AssetItem.objects.create(
            asset_tag="EXIST-001", asset_type=self.atype,
            brand="Dell", model_name="Latitude 5540", serial_number="SN-TAKEN",
        )

    def _form_data(self, **overrides):
        data = {
            "asset_type": self.atype.pk,
            "brand": "Dell",
            "model_name": "Latitude 5540",
            "serial_number": "SN-FREE",
            "spec_cpu": "i5",
        }
        data.update(overrides)
        return data

    def test_create_rejects_duplicate_serial(self):
        resp = self.client.post("/new/", self._form_data(serial_number="SN-TAKEN"))
        self.assertEqual(resp.status_code, 200)  # re-rendered, not redirected
        self.assertContains(resp, "EXIST-001")
        self.assertContains(resp, "must be unique")
        self.assertEqual(AssetItem.objects.filter(serial_number="SN-TAKEN").count(), 1)

    def test_create_rejects_duplicate_serial_in_different_case(self):
        resp = self.client.post("/new/", self._form_data(serial_number="sn-taken"))
        self.assertContains(resp, "must be unique")
        self.assertEqual(AssetItem.objects.count(), 1)

    def test_create_accepts_free_serial(self):
        resp = self.client.post("/new/", self._form_data(serial_number="SN-FREE"))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AssetItem.objects.filter(serial_number="SN-FREE").exists())

    def test_edit_rejects_serial_owned_by_another_asset(self):
        other = AssetItem.objects.create(
            asset_tag="EXIST-002", asset_type=self.atype,
            brand="Dell", model_name="Latitude 5540", serial_number="SN-OTHER",
        )
        resp = self.client.post(
            f"/{other.pk}/edit/", self._form_data(serial_number="SN-TAKEN")
        )
        self.assertContains(resp, "must be unique")
        other.refresh_from_db()
        self.assertEqual(other.serial_number, "SN-OTHER")

    def test_edit_allows_asset_to_keep_its_own_serial(self):
        resp = self.client.post(
            f"/{self.existing.pk}/edit/",
            self._form_data(serial_number="SN-TAKEN", model_name="Latitude 5550"),
        )
        self.assertEqual(resp.status_code, 302)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.model_name, "Latitude 5550")

    def _bulk_post(self, serials):
        return self.client.post("/bulk-add/", {
            "asset_type": self.atype.pk,
            "brand": "Dell",
            "model_name": "Latitude 5540",
            "quantity": str(len(serials)),
            "serial_numbers": "\n".join(serials),
            "spec_cpu": "i5",
        })

    def test_bulk_add_rejects_serial_already_in_system(self):
        resp = self._bulk_post(["SN-A", "SN-TAKEN", "SN-B"])
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Line 2")
        self.assertContains(resp, "EXIST-001")
        # Nothing created — the whole batch is rejected.
        self.assertEqual(AssetItem.objects.count(), 1)

    def test_bulk_add_rejects_serial_repeated_within_the_list(self):
        resp = self._bulk_post(["SN-A", "SN-B", "sn-a"])
        self.assertContains(resp, "Line 3")
        self.assertContains(resp, "repeats the serial number on line 1")
        self.assertEqual(AssetItem.objects.count(), 1)

    def test_bulk_add_accepts_distinct_free_serials(self):
        resp = self._bulk_post(["SN-A", "SN-B", "SN-C"])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(AssetItem.objects.count(), 4)

    def test_serial_check_endpoint_reports_conflict(self):
        resp = self.client.get("/serial-check/", {"serial_number": "sn-taken"})
        self.assertContains(resp, "EXIST-001")

    def test_serial_check_endpoint_reports_available(self):
        resp = self.client.get("/serial-check/", {"serial_number": "SN-NOBODY"})
        self.assertContains(resp, "Available")

    def test_serial_check_excludes_the_asset_being_edited(self):
        resp = self.client.get(
            "/serial-check/",
            {"serial_number": "SN-TAKEN", "exclude_pk": str(self.existing.pk)},
        )
        self.assertContains(resp, "Available")


class ExcelImportSerialUniquenessTests(TestCase):
    """Duplicate serials are import errors, both against the DB and in-file."""

    def setUp(self):
        self.asset_type = make_import_type(spec_schema=["cpu", "ram"])
        self.building, self.floor, self.room = make_location_hierarchy()
        self.headers = _base_headers(self.asset_type)

    def _validate(self, rows):
        f = make_excel_file(self.headers, rows)
        return ExcelImportValidator().validate(f, self.asset_type.pk)

    def test_serial_already_in_system_fails(self):
        AssetItem.objects.create(
            asset_tag="IMP-EXIST", asset_type=self.asset_type,
            brand="Dell", model_name="Latitude", serial_number="SN-TEST-001",
        )
        row = _valid_row_values()  # serial_number is "SN-TEST-001"
        results = self._validate([row])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(any("IMP-EXIST" in e for e in results[0]["errors"]))

    def test_serial_of_soft_deleted_asset_is_free(self):
        gone = AssetItem.objects.create(
            asset_tag="IMP-GONE", asset_type=self.asset_type,
            brand="Dell", model_name="Latitude", serial_number="SN-TEST-001",
        )
        gone.soft_delete()
        results = self._validate([_valid_row_values(self.room.full_path)])
        self.assertEqual(results[0]["status"], "valid")

    def test_serial_repeated_within_the_file_fails(self):
        first = _valid_row_values(self.room.full_path)
        second = _valid_row_values(self.room.full_path)
        second[1] = first[1].lower()  # same serial, different case
        results = self._validate([first, second])
        self.assertEqual(results[0]["status"], "valid")
        self.assertEqual(results[1]["status"], "error")
        self.assertTrue(any("repeated in this file" in e for e in results[1]["errors"]))


class PlaceholderSerialTests(TestCase):
    """"UNKNOWN" and friends mean "no serial" — they may repeat."""

    def setUp(self):
        self.atype = make_type()

    def _item(self, tag, serial):
        return AssetItem.objects.create(
            asset_tag=tag, asset_type=self.atype,
            brand="Dell", model_name="Latitude 5540", serial_number=serial,
        )

    def test_placeholder_helper_recognises_blank_and_words(self):
        for value in ("", "   ", "UNKNOWN", "unknown", " Unknown ", "N/A", "na", "-", "?"):
            self.assertTrue(is_placeholder_serial(value), value)
        for value in ("SN-001", "UNKNOWN-1", "NA1"):
            self.assertFalse(is_placeholder_serial(value), value)

    def test_placeholder_serials_may_repeat(self):
        self._item("PH-001", "UNKNOWN")
        self._item("PH-002", "Unknown")
        self._item("PH-003", "N/A")
        self.assertEqual(AssetItem.objects.count(), 3)

    def test_placeholder_passes_full_clean(self):
        self._item("PH-001", "UNKNOWN")
        second = AssetItem(
            asset_tag="PH-002", asset_type=self.atype,
            brand="Dell", model_name="Latitude 5540", serial_number="UNKNOWN",
        )
        second.full_clean()  # must not raise

    def test_real_serial_still_unique_alongside_placeholders(self):
        from django.db import IntegrityError
        self._item("PH-001", "UNKNOWN")
        self._item("PH-002", "SN-REAL")
        with self.assertRaises(IntegrityError):
            self._item("PH-003", "SN-REAL")


class PlaceholderSerialFormTests(TestCase):
    def setUp(self):
        self.client.force_login(_role_user("ph-officer", "IT Officer"))
        self.atype = make_type(category=make_category("Computing"), name="Laptop")
        SubAssetSpecField.objects.create(
            sub_asset=self.atype, key="cpu", label="CPU", widget="text",
        )
        AssetItem.objects.create(
            asset_tag="PH-EXIST", asset_type=self.atype,
            brand="Dell", model_name="Latitude 5540", serial_number="UNKNOWN",
        )

    def test_create_accepts_repeated_placeholder(self):
        resp = self.client.post("/new/", {
            "asset_type": self.atype.pk, "brand": "Dell",
            "model_name": "Latitude 5540", "serial_number": "unknown", "spec_cpu": "i5",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(AssetItem.objects.count(), 2)

    def test_bulk_add_accepts_repeated_placeholders(self):
        resp = self.client.post("/bulk-add/", {
            "asset_type": self.atype.pk, "brand": "Dell",
            "model_name": "Latitude 5540", "quantity": "3",
            "serial_numbers": "UNKNOWN\nUnknown\nN/A", "spec_cpu": "i5",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(AssetItem.objects.count(), 4)

    def test_serial_check_marks_placeholder_as_unchecked(self):
        resp = self.client.get("/serial-check/", {"serial_number": "UNKNOWN"})
        self.assertContains(resp, "not checked for duplicates")


class ExcelImportPlaceholderSerialTests(TestCase):
    def setUp(self):
        self.asset_type = make_import_type(spec_schema=["cpu", "ram"])
        self.building, self.floor, self.room = make_location_hierarchy()
        self.headers = _base_headers(self.asset_type)

    def _validate(self, rows):
        return ExcelImportValidator().validate(
            make_excel_file(self.headers, rows), self.asset_type.pk
        )

    def test_repeated_placeholder_rows_are_warnings_not_errors(self):
        AssetItem.objects.create(
            asset_tag="IMP-PH", asset_type=self.asset_type,
            brand="Dell", model_name="Latitude", serial_number="UNKNOWN",
        )
        first = _valid_row_values(self.room.full_path)
        first[1] = "UNKNOWN"
        second = _valid_row_values(self.room.full_path)
        second[1] = "unknown"
        results = self._validate([first, second])
        for result in results:
            self.assertEqual(result["status"], "warning")
            self.assertEqual(result["errors"], [])
            self.assertTrue(any("no serial" in w for w in result["warnings"]))
