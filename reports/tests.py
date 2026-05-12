"""
Tests for the reports app: Excel byte output and view HTTP responses.
WeasyPrint is not exercised in tests (no display server in CI) — PDF views
are smoke-tested for import and URL resolution only.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from assets.models import AssetCategory, AssetItem, AssetType
from assignees.models import Assignee, AssigneeType, CachedEmployee
from assignments.models import Assignment
from lifecycle.models import EventType, LifecycleEvent
from locations.models import Location

User = get_user_model()

XLSX_MAGIC = b"PK"  # .xlsx files are ZIP archives


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_asset(tag="TST-001", status=AssetItem.Status.IN_STOCK, user=None):
    cat, _ = AssetCategory.objects.get_or_create(name="Test Cat")
    atype, _ = AssetType.objects.get_or_create(
        category=cat, name="Test Type", defaults={"spec_schema": []}
    )
    return AssetItem.objects.create(
        asset_tag=tag,
        asset_type=atype,
        brand="Acme",
        model_name="X1",
        status=status,
        created_by=user,
    )


def _make_user(username="tester"):
    return User.objects.create_user(username=username, password="testpass123!", is_superuser=True, is_staff=True)


def _make_assignee(user):
    emp = CachedEmployee.objects.create(
        name_en="Test Employee",
        source="MANUAL",
    )
    return Assignee.objects.create(
        assignee_type=AssigneeType.EMPLOYEE,
        employee=emp,
    )


def _make_assignment(asset, assignee, user):
    snap = assignee.build_snapshot()
    return Assignment.objects.create(
        asset=asset,
        assignee=assignee,
        performed_by=user,
        holder_snapshot=snap,
    )


# ── Excel generator unit tests ─────────────────────────────────────────────

class InventoryExcelTest(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.asset = _make_asset(user=self.user)

    def test_returns_bytes(self):
        from reports.generators.excel import inventory_excel
        result = inventory_excel()
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(XLSX_MAGIC))

    def test_with_status_filter(self):
        from reports.generators.excel import inventory_excel
        result = inventory_excel({"status": "IN_STOCK"})
        self.assertTrue(result.startswith(XLSX_MAGIC))

    def test_empty_inventory(self):
        from reports.generators.excel import inventory_excel
        AssetItem.objects.all().delete()
        result = inventory_excel()
        self.assertTrue(result.startswith(XLSX_MAGIC))


class TransferLogExcelTest(TestCase):
    def setUp(self):
        self.user = _make_user("tloguser")
        asset = _make_asset("TL-001", user=self.user)
        asgn = _make_assignee(self.user)
        _make_assignment(asset, asgn, self.user)

    def test_returns_bytes(self):
        from reports.generators.excel import transfer_log_excel
        result = transfer_log_excel()
        self.assertTrue(result.startswith(XLSX_MAGIC))

    def test_date_filter(self):
        from reports.generators.excel import transfer_log_excel
        result = transfer_log_excel(
            date_from=date.today() - timedelta(days=7),
            date_to=date.today(),
        )
        self.assertTrue(result.startswith(XLSX_MAGIC))


class LifecycleEventsExcelTest(TestCase):
    def setUp(self):
        self.user = _make_user("lcuser")
        asset = _make_asset("LC-001", user=self.user)
        asset.status = AssetItem.Status.MAINTENANCE
        asset.save()
        LifecycleEvent.objects.create(
            asset=asset,
            event_type=EventType.MAINTENANCE_SENT,
            old_status=AssetItem.Status.IN_STOCK,
            new_status=AssetItem.Status.MAINTENANCE,
            performed_by=self.user,
        )

    def test_returns_bytes(self):
        from reports.generators.excel import lifecycle_events_excel
        result = lifecycle_events_excel()
        self.assertTrue(result.startswith(XLSX_MAGIC))

    def test_event_type_filter(self):
        from reports.generators.excel import lifecycle_events_excel
        result = lifecycle_events_excel(event_type=EventType.MAINTENANCE_SENT)
        self.assertTrue(result.startswith(XLSX_MAGIC))


class WarrantyExcelTest(TestCase):
    def setUp(self):
        user = _make_user("wtyuser")
        asset = _make_asset("WTY-001", user=user)
        asset.warranty_expiry = date.today() + timedelta(days=30)
        asset.save()

    def test_returns_bytes(self):
        from reports.generators.excel import warranty_expiry_excel
        result = warranty_expiry_excel(days=90)
        self.assertTrue(result.startswith(XLSX_MAGIC))

    def test_no_expiring(self):
        from reports.generators.excel import warranty_expiry_excel
        result = warranty_expiry_excel(days=1)
        self.assertTrue(result.startswith(XLSX_MAGIC))


class AssetHistoryExcelTest(TestCase):
    def setUp(self):
        self.user = _make_user("ahuser")
        self.asset = _make_asset("AH-001", user=self.user)
        asgn = _make_assignee(self.user)
        _make_assignment(self.asset, asgn, self.user)

    def test_returns_bytes(self):
        from reports.generators.excel import asset_history_excel
        result = asset_history_excel(self.asset.pk)
        self.assertTrue(result.startswith(XLSX_MAGIC))

    def test_no_history(self):
        from reports.generators.excel import asset_history_excel
        empty_asset = _make_asset("AH-002", user=self.user)
        result = asset_history_excel(empty_asset.pk)
        self.assertTrue(result.startswith(XLSX_MAGIC))


# ── View tests ────────────────────────────────────────────────────────────────

class ReportViewsTest(TestCase):
    def setUp(self):
        self.user = _make_user("viewuser")
        self.client = Client()
        self.client.login(username="viewuser", password="testpass123!")
        self.asset = _make_asset("VW-001", user=self.user)
        asgn = _make_assignee(self.user)
        self.assignment = _make_assignment(self.asset, asgn, self.user)

    def test_report_index_200(self):
        resp = self.client.get(reverse("reports:index"))
        self.assertEqual(resp.status_code, 200)

    def test_inventory_excel_download(self):
        resp = self.client.get(reverse("reports:inventory_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])

    def test_transfer_log_excel_download(self):
        resp = self.client.get(reverse("reports:transfer_log_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])

    def test_lifecycle_excel_download(self):
        resp = self.client.get(reverse("reports:lifecycle_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])

    def test_warranty_excel_download(self):
        resp = self.client.get(reverse("reports:warranty_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])

    def test_asset_history_excel_download(self):
        resp = self.client.get(
            reverse("reports:asset_history_excel", kwargs={"pk": self.asset.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])

    def test_asset_history_404_for_missing(self):
        resp = self.client.get(
            reverse("reports:asset_history_excel", kwargs={"pk": 99999})
        )
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_redirects(self):
        anon = Client()
        resp = anon.get(reverse("reports:index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/", resp["Location"])

    def test_inventory_excel_status_filter(self):
        resp = self.client.get(
            reverse("reports:inventory_excel") + "?status=IN_STOCK"
        )
        self.assertEqual(resp.status_code, 200)

    def test_warranty_excel_days_param(self):
        resp = self.client.get(reverse("reports:warranty_excel") + "?days=180")
        self.assertEqual(resp.status_code, 200)

    def test_warranty_excel_invalid_days_defaults(self):
        resp = self.client.get(reverse("reports:warranty_excel") + "?days=abc")
        self.assertEqual(resp.status_code, 200)

    @patch("reports.views.handover_pdf", return_value=b"%PDF-1.4 test")
    def test_handover_pdf_download(self, mock_pdf):
        resp = self.client.get(
            reverse("reports:handover_pdf", kwargs={"pk": self.assignment.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    @patch("reports.views.disposal_pdf", return_value=b"%PDF-1.4 test")
    def test_disposal_pdf_download(self, mock_pdf):
        resp = self.client.get(
            reverse("reports:disposal_pdf", kwargs={"pk": self.asset.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    @patch("reports.views.handover_pdf", return_value=b"%PDF-1.4 test")
    def test_handover_404_for_missing(self, mock_pdf):
        resp = self.client.get(
            reverse("reports:handover_pdf", kwargs={"pk": 99999})
        )
        self.assertEqual(resp.status_code, 404)
