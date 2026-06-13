from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from assets.models import AssetCategory, AssetItem, AssetType
from assignments.models import Assignment
from assignees.models import Assignee, AssigneeType, CachedEmployee
from lifecycle.models import EventType, LifecycleEvent
from locations.models import Location

from .middleware import set_current_user
from .models import AuditLog
from .services import format_changes, record

User = get_user_model()


def _role_user(username, group):
    u = User.objects.create_user(username=username, password="pw12345!")
    grp, _ = Group.objects.get_or_create(name=group)
    u.groups.add(grp)
    return u


def _category():
    return AssetCategory.objects.create(name="Computing")


def _type(category=None):
    return AssetType.objects.create(
        category=category or _category(), name="Laptop", spec_schema=["cpu"],
    )


class SignalCaptureTests(TestCase):
    def setUp(self):
        self.user = _role_user("editor", "IT Officer")
        set_current_user(self.user)
        self.addCleanup(set_current_user, None)

    def test_create_is_logged(self):
        t = _type()
        log = AuditLog.objects.filter(target_model="assets.AssetType", action="CREATE").latest("created_at")
        self.assertEqual(log.actor, self.user)
        self.assertIn("name", log.changes)
        self.assertEqual(log.changes["name"], [None, "Laptop"])

    def test_update_diffs_only_changed_fields(self):
        t = _type()
        AuditLog.objects.all().delete()
        t.name = "Notebook"
        t.save()
        log = AuditLog.objects.get(target_model="assets.AssetType", action="UPDATE")
        self.assertEqual(set(log.changes.keys()), {"name"})
        self.assertEqual(log.changes["name"], ["Laptop", "Notebook"])

    def test_no_log_when_nothing_tracked_changed(self):
        item = AssetItem.objects.create(
            asset_tag="LAP-1", asset_type=_type(), brand="Dell", model_name="X",
        )
        AuditLog.objects.all().delete()
        # status is excluded from AssetItem diffing → no UPDATE entry
        item.status = AssetItem.Status.MAINTENANCE
        item.save()
        self.assertFalse(AuditLog.objects.filter(action="UPDATE").exists())

    def test_actor_is_system_without_request_user(self):
        set_current_user(None)
        _type()
        log = AuditLog.objects.filter(action="CREATE").latest("created_at")
        self.assertIsNone(log.actor)
        self.assertEqual(log.actor_label, "System")

    def test_hard_delete_logged(self):
        loc = Location.objects.create(name="Room 1", level_type="ROOM")
        AuditLog.objects.all().delete()
        loc.delete()
        self.assertTrue(AuditLog.objects.filter(action="DELETE", target_model="locations.Location").exists())


class StatusAndOwnershipTests(TestCase):
    def setUp(self):
        self.user = _role_user("officer", "IT Officer")
        self.item = AssetItem.objects.create(
            asset_tag="PC-1", asset_type=_type(), brand="Dell", model_name="Opti",
        )

    def test_lifecycle_event_logs_status(self):
        LifecycleEvent.objects.create(
            asset=self.item, event_type=EventType.MAINTENANCE_SENT,
            old_status="IN_STOCK", new_status="MAINTENANCE", performed_by=self.user,
        )
        log = AuditLog.objects.get(action="STATUS", target_id=str(self.item.pk))
        self.assertEqual(log.changes["status"], ["IN_STOCK", "MAINTENANCE"])
        self.assertEqual(log.actor, self.user)

    def test_assignment_logs_assign(self):
        emp = CachedEmployee.objects.create(prp_id="E1", name_en="Jane")
        assignee = Assignee.objects.create(assignee_type=AssigneeType.EMPLOYEE, employee=emp)
        Assignment.objects.create(asset=self.item, assignee=assignee, performed_by=self.user)
        self.assertTrue(
            AuditLog.objects.filter(action="ASSIGN", target_id=str(self.item.pk)).exists()
        )


class ActivityLogViewTests(TestCase):
    def test_requires_admin(self):
        self.client.force_login(_role_user("v", "Viewer"))
        self.assertEqual(self.client.get("/activity/").status_code, 403)

    def test_admin_can_view(self):
        self.client.force_login(_role_user("a", "Admin"))
        self.assertEqual(self.client.get("/activity/").status_code, 200)


class FormatChangesTests(TestCase):
    def test_booleans_and_dicts(self):
        rows = format_changes({"is_active": [True, False], "name": [None, "X"]})
        self.assertEqual(rows[0], {"field": "Active", "before": "Yes", "after": "No"})
        self.assertEqual(rows[1]["before"], "—")
