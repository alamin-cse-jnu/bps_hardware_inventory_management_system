from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from assets.models import AssetCategory, AssetComponent, AssetItem, AssetType
from assignees.models import Assignee, AssigneeType, CachedEmployee, Source
from assignments.models import Assignment
from assignments.services import perform_transfer

from django.contrib.auth.models import Group

from .models import EventType, LifecycleEvent
from .services import (
    add_component,
    dispose_asset,
    recover_asset,
    remove_component,
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


# ── add_component / remove_component ──────────────────────────────────────────

class AddRemoveComponentTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.asset = make_asset(tag="PC-010", has_components=True)

    def test_add_creates_active_component_and_event(self):
        ev = add_component(
            self.asset, AssetComponent.ComponentType.SFP,
            brand="Cisco", model="GLC-SX-MMD", serial="SFP-1",
            performed_by=self.user, note="Fibre uplink",
        )
        self.assertEqual(ev.event_type, EventType.COMPONENT_ADD)
        self.assertIsNotNone(ev.component)
        self.assertTrue(ev.component.is_active)
        self.assertEqual(self.asset.components.filter(is_active=True).count(), 1)
        # status untouched
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetItem.Status.IN_STOCK)

    def test_add_rejected_when_type_has_no_components(self):
        plain = make_asset(tag="LAP-1", has_components=False)
        with self.assertRaises(ValidationError):
            add_component(
                plain, AssetComponent.ComponentType.RAM,
                brand="X", model="Y", serial="Z", performed_by=self.user,
            )

    def test_remove_marks_inactive_with_reason(self):
        comp = AssetComponent.objects.create(
            parent_asset=self.asset,
            component_type=AssetComponent.ComponentType.STORAGE_DRIVE,
            brand="Samsung", model_name="870 EVO", serial_number="SSD-1",
            is_active=True,
        )
        ev = remove_component(self.asset, comp, self.user, note="Failed drive")
        comp.refresh_from_db()
        self.assertFalse(comp.is_active)
        self.assertIsNotNone(comp.removed_at)
        self.assertEqual(comp.removal_reason, "Failed drive")
        self.assertEqual(ev.event_type, EventType.COMPONENT_REMOVE)

    def test_remove_rejects_wrong_asset(self):
        other = make_asset(tag="PC-011", has_components=True)
        comp = AssetComponent.objects.create(
            parent_asset=self.asset,
            component_type=AssetComponent.ComponentType.RAM,
            brand="A", model_name="B", is_active=True,
        )
        with self.assertRaises(ValidationError):
            remove_component(other, comp, self.user)

    def test_remove_rejects_already_removed(self):
        comp = AssetComponent.objects.create(
            parent_asset=self.asset,
            component_type=AssetComponent.ComponentType.RAM,
            brand="A", model_name="B", is_active=False,
        )
        with self.assertRaises(ValidationError):
            remove_component(self.asset, comp, self.user)


# ── component_panel view ──────────────────────────────────────────────────────

class ComponentPanelViewTests(TestCase):

    def setUp(self):
        self.asset = make_asset(tag="PC-020", has_components=True)
        officer = User.objects.create_user(username="off", password="pw")
        grp, _ = Group.objects.get_or_create(name="IT Officer")
        officer.groups.add(grp)
        self.client.force_login(officer)
        self.url = f"/lifecycle/{self.asset.pk}/components/"

    def test_get_renders_panel(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Manage Components")

    def test_post_add_then_replace_then_remove(self):
        # add
        r = self.client.post(self.url, {
            "action": "add", "component_type": "RAM",
            "brand": "Kingston", "model_name": "8GB", "serial_number": "K1",
        })
        self.assertEqual(r.status_code, 200)
        comp = self.asset.components.get(is_active=True)
        # replace
        self.client.post(self.url, {
            "action": "replace", "old_component_id": comp.pk,
            "component_type": "RAM", "brand": "Corsair", "model_name": "16GB",
            "serial_number": "C1", "note": "upgrade",
        })
        comp.refresh_from_db()
        self.assertFalse(comp.is_active)
        new = self.asset.components.get(is_active=True)
        self.assertEqual(new.brand, "Corsair")
        # remove
        self.client.post(self.url, {"action": "remove", "component_id": new.pk, "note": "pull"})
        self.assertEqual(self.asset.components.filter(is_active=True).count(), 0)
        self.assertEqual(self.asset.components.filter(is_active=False).count(), 2)

    def test_viewer_forbidden(self):
        viewer = User.objects.create_user(username="vw", password="pw")
        grp, _ = Group.objects.get_or_create(name="Viewer")
        viewer.groups.add(grp)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)


# ── LifecycleEvent str ────────────────────────────────────────────────────────

class LifecycleEventStrTests(TestCase):

    def test_str_contains_event_type_and_tag(self):
        user = make_user()
        asset = make_asset(status=AssetItem.Status.IN_STOCK)
        ev = send_to_maintenance(asset, user)
        self.assertIn("Sent to Maintenance", str(ev))
        self.assertIn(asset.asset_tag, str(ev))
