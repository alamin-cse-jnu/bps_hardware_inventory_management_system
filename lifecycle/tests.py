from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from assets.models import AssetCategory, AssetComponent, AssetItem, AssetType
from assignees.models import Assignee, AssigneeType, CachedEmployee, Source
from assignments.models import Assignment
from assignments.services import perform_transfer

from .models import EventType, LifecycleEvent
from .services import (
    dispose_asset,
    recover_asset,
    repair_asset,
    report_damaged,
    report_lost,
    return_from_maintenance,
    send_to_maintenance,
    swap_component,
)

User = get_user_model()


# ── helpers ───────────────────────────────────────────────────────────────────

def make_user(username="officer"):
    return User.objects.create_user(username=username, password="pw")


def make_asset(tag="PC-001", status=AssetItem.Status.IN_STOCK, has_components=False):
    cat, _ = AssetCategory.objects.get_or_create(name="Computing")
    atype, _ = AssetType.objects.get_or_create(
        category=cat, name="Laptop" if not has_components else "PC Set",
        defaults={"spec_schema": [], "has_components": has_components},
    )
    if has_components:
        atype.has_components = True
        atype.save(update_fields=["has_components"])
    return AssetItem.objects.create(
        asset_tag=tag, asset_type=atype,
        brand="Dell", model_name="Test",
        status=status,
    )


def make_assignee():
    emp = CachedEmployee.objects.create(
        name_en="Test User", source=Source.MANUAL,
        office_name_en="IT Dept",
    )
    return Assignee.objects.create(assignee_type=AssigneeType.EMPLOYEE, employee=emp)


# ── send_to_maintenance ───────────────────────────────────────────────────────

class SendToMaintenanceTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_from_in_stock(self):
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        ev = send_to_maintenance(asset, self.user, note="Annual servicing")
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.MAINTENANCE)
        self.assertEqual(ev.event_type, EventType.MAINTENANCE_SENT)
        self.assertEqual(ev.old_status, AssetItem.Status.IN_STOCK)
        self.assertEqual(ev.new_status, AssetItem.Status.MAINTENANCE)

    def test_from_assigned_closes_assignment(self):
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        assignee = make_assignee()
        asgn = perform_transfer(asset, assignee, self.user)

        send_to_maintenance(asset, self.user)

        asgn.refresh_from_db()
        self.assertIsNotNone(asgn.returned_at)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.MAINTENANCE)

    def test_from_damaged(self):
        asset = make_asset(status=AssetItem.Status.DAMAGED)
        ev = send_to_maintenance(asset, self.user)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.MAINTENANCE)
        self.assertEqual(ev.old_status, AssetItem.Status.DAMAGED)

    def test_raises_from_maintenance(self):
        asset = make_asset(status=AssetItem.Status.MAINTENANCE)
        with self.assertRaises(ValidationError):
            send_to_maintenance(asset, self.user)

    def test_raises_from_disposed(self):
        asset = make_asset(status=AssetItem.Status.DISPOSED)
        with self.assertRaises(ValidationError):
            send_to_maintenance(asset, self.user)


# ── return_from_maintenance ───────────────────────────────────────────────────

class ReturnFromMaintenanceTests(TestCase):

    def test_maintenance_to_in_stock(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.MAINTENANCE)
        ev = return_from_maintenance(asset, user, note="Repaired by vendor")
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.IN_STOCK)
        self.assertEqual(ev.event_type, EventType.MAINTENANCE_RETURN)

    def test_raises_if_not_in_maintenance(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        with self.assertRaises(ValidationError):
            return_from_maintenance(asset, user)


# ── report_lost ───────────────────────────────────────────────────────────────

class ReportLostTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.asset = make_asset(status=AssetItem.Status.IN_STOCK)
        self.assignee = make_assignee()
        perform_transfer(self.asset, self.assignee, self.user)

    def test_assigned_to_lost(self):
        ev = report_lost(self.asset, self.user, note="Incident #42")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetItem.Status.LOST)
        self.assertEqual(ev.event_type, EventType.LOST)

    def test_closes_assignment(self):
        asgn = Assignment.objects.get(asset=self.asset, returned_at__isnull=True)
        report_lost(self.asset, self.user)
        asgn.refresh_from_db()
        self.assertIsNotNone(asgn.returned_at)

    def test_raises_if_not_assigned(self):
        asset2 = make_asset(tag="PC-002", status=AssetItem.Status.IN_STOCK)
        with self.assertRaises(ValidationError):
            report_lost(asset2, self.user)


# ── report_damaged ────────────────────────────────────────────────────────────

class ReportDamagedTests(TestCase):

    def test_assigned_to_damaged(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        assignee = make_assignee()
        perform_transfer(asset, assignee, user)
        ev = report_damaged(asset, user, note="Screen cracked")
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.DAMAGED)
        self.assertEqual(ev.event_type, EventType.DAMAGED)

    def test_raises_if_in_stock(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        with self.assertRaises(ValidationError):
            report_damaged(asset, user)


# ── recover_asset ─────────────────────────────────────────────────────────────

class RecoverAssetTests(TestCase):

    def test_lost_to_in_stock(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.LOST)
        ev = recover_asset(asset, user, note="Found in storage room")
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.IN_STOCK)
        self.assertEqual(ev.event_type, EventType.RECOVERED)

    def test_raises_if_not_lost(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        with self.assertRaises(ValidationError):
            recover_asset(asset, user)


# ── repair_asset ──────────────────────────────────────────────────────────────

class RepairAssetTests(TestCase):

    def test_damaged_to_in_stock(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.DAMAGED)
        ev = repair_asset(asset, user)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.IN_STOCK)
        self.assertEqual(ev.event_type, EventType.REPAIRED)

    def test_raises_if_not_damaged(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.MAINTENANCE)
        with self.assertRaises(ValidationError):
            repair_asset(asset, user)


# ── dispose_asset ─────────────────────────────────────────────────────────────

class DisposeAssetTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_in_stock_to_disposed(self):
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        ev = dispose_asset(asset, self.user, note="End of life")
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.DISPOSED)
        self.assertEqual(ev.event_type, EventType.DISPOSED)

    def test_assigned_to_disposed_closes_assignment(self):
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        assignee = make_assignee()
        asgn = perform_transfer(asset, assignee, self.user)
        dispose_asset(asset, self.user)
        asgn.refresh_from_db()
        self.assertIsNotNone(asgn.returned_at)

    def test_maintenance_to_disposed(self):
        asset = make_asset(status=AssetItem.Status.MAINTENANCE)
        dispose_asset(asset, self.user)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.DISPOSED)

    def test_lost_to_disposed(self):
        asset = make_asset(status=AssetItem.Status.LOST)
        dispose_asset(asset, self.user)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.DISPOSED)

    def test_damaged_to_disposed(self):
        asset = make_asset(status=AssetItem.Status.DAMAGED)
        dispose_asset(asset, self.user)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetItem.Status.DISPOSED)

    def test_raises_if_already_disposed(self):
        asset = make_asset(status=AssetItem.Status.DISPOSED)
        with self.assertRaises(ValidationError):
            dispose_asset(asset, self.user)


# ── swap_component ────────────────────────────────────────────────────────────

class SwapComponentTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.asset = make_asset(tag="PC-003", has_components=True)
        self.old_comp = AssetComponent.objects.create(
            parent_asset=self.asset,
            component_type=AssetComponent.ComponentType.RAM,
            brand="Kingston", model_name="8GB DDR4",
            serial_number="KVR-001",
            is_active=True,
        )

    def test_swap_creates_new_component(self):
        ev = swap_component(
            self.asset, self.old_comp,
            new_component_type=AssetComponent.ComponentType.RAM,
            new_brand="Corsair", new_model="16GB DDR5",
            new_serial="CMK-001",
            performed_by=self.user, note="Upgraded RAM",
        )
        self.old_comp.refresh_from_db()
        self.assertFalse(self.old_comp.is_active)
        self.assertIsNotNone(self.old_comp.removed_at)
        self.assertIsNotNone(ev.component)
        self.assertEqual(ev.component.brand, "Corsair")
        self.assertEqual(ev.event_type, EventType.COMPONENT_SWAP)

    def test_asset_status_unchanged_after_swap(self):
        original_status = self.asset.status
        swap_component(
            self.asset, self.old_comp,
            new_component_type=AssetComponent.ComponentType.RAM,
            new_brand="G.Skill", new_model="16GB DDR5",
            new_serial="GSK-001",
            performed_by=self.user,
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, original_status)

    def test_raises_if_wrong_asset(self):
        other_asset = make_asset(tag="PC-004", has_components=True)
        with self.assertRaises(ValidationError):
            swap_component(
                other_asset, self.old_comp,
                new_component_type=AssetComponent.ComponentType.RAM,
                new_brand="G.Skill", new_model="8GB", new_serial="GS-001",
                performed_by=self.user,
            )


# ── LifecycleEvent str ────────────────────────────────────────────────────────

class LifecycleEventStrTests(TestCase):

    def test_str_contains_event_type_and_tag(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        ev = send_to_maintenance(asset, user)
        self.assertIn("Sent to Maintenance", str(ev))
        self.assertIn(asset.asset_tag, str(ev))
