from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from assets.models import AssetCategory, AssetItem, AssetType
from assignees.models import Assignee, AssigneeType, CachedEmployee, Source
from locations.models import Location

from .models import AlertStatus, Assignment, InactiveHolderAlert, TransferBatch
from .services import perform_transfer, return_to_stock

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_user(username="testuser") -> User:
    return User.objects.create_user(username=username, password="password123")


def make_asset(tag="PC-2024-0001", status=AssetItem.Status.IN_STOCK) -> AssetItem:
    cat, _ = AssetCategory.objects.get_or_create(name="Computing")
    atype, _ = AssetType.objects.get_or_create(
        category=cat,
        name="Laptop",
        defaults={"spec_schema": []},
    )
    return AssetItem.objects.create(
        asset_tag=tag,
        asset_type=atype,
        brand="Dell",
        model_name="Latitude",
        status=status,
    )


def make_employee_assignee(name="Md. Karim") -> Assignee:
    emp = CachedEmployee.objects.create(
        name_en=name,
        source=Source.MANUAL,
        section_name_en="IT Section",
        office_name_en="Parliament Secretariat",
    )
    return Assignee.objects.create(assignee_type=AssigneeType.EMPLOYEE, employee=emp)


# ─────────────────────────────────────────────────────────────────────────────
# TransferBatch
# ─────────────────────────────────────────────────────────────────────────────

class TransferBatchTests(TestCase):

    def test_generate_reference_first(self):
        user = make_user()
        ref = TransferBatch.generate_reference()
        year = timezone.now().year
        self.assertTrue(ref.startswith(f"TB-{year}-"))
        self.assertEqual(ref, f"TB-{year}-0001")

    def test_generate_reference_increments(self):
        user = make_user()
        year = timezone.now().year
        TransferBatch.objects.create(
            reference=f"TB-{year}-0005", performed_by=user,
        )
        ref = TransferBatch.generate_reference()
        self.assertEqual(ref, f"TB-{year}-0006")

    def test_reference_unique(self):
        user = make_user()
        year = timezone.now().year
        TransferBatch.objects.create(reference=f"TB-{year}-0001", performed_by=user)
        with self.assertRaises(Exception):
            TransferBatch.objects.create(reference=f"TB-{year}-0001", performed_by=user)


# ─────────────────────────────────────────────────────────────────────────────
# Assignment model
# ─────────────────────────────────────────────────────────────────────────────

class AssignmentModelTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.asset = make_asset()
        self.assignee = make_employee_assignee()

    def test_active_assignment_has_null_returned_at(self):
        a = Assignment.objects.create(
            asset=self.asset,
            assignee=self.assignee,
            holder_snapshot=self.assignee.build_snapshot(),
            performed_by=self.user,
        )
        self.assertTrue(a.is_active)
        self.assertIsNone(a.returned_at)

    def test_immutability_after_returned_at_set(self):
        a = Assignment.objects.create(
            asset=self.asset,
            assignee=self.assignee,
            holder_snapshot=self.assignee.build_snapshot(),
            performed_by=self.user,
        )
        # Close the assignment legitimately via update()
        Assignment.objects.filter(pk=a.pk).update(
            returned_at=timezone.now(), updated_at=timezone.now()
        )
        # Re-fetch from DB
        a.refresh_from_db()
        # Now try to save — must raise ValidationError
        a.notes = "Attempted modification"
        with self.assertRaises(ValidationError) as ctx:
            a.save()
        self.assertIn("closed", str(ctx.exception).lower())

    def test_setting_returned_at_for_first_time_is_allowed(self):
        a = Assignment.objects.create(
            asset=self.asset,
            assignee=self.assignee,
            holder_snapshot=self.assignee.build_snapshot(),
            performed_by=self.user,
        )
        # Close via update() (as services.py does)
        Assignment.objects.filter(pk=a.pk).update(
            returned_at=timezone.now(), updated_at=timezone.now()
        )
        a.refresh_from_db()
        self.assertIsNotNone(a.returned_at)
        self.assertFalse(a.is_active)

    def test_str_active(self):
        a = Assignment.objects.create(
            asset=self.asset,
            assignee=self.assignee,
            holder_snapshot={},
            performed_by=self.user,
        )
        self.assertIn("active", str(a))

    def test_str_returned(self):
        a = Assignment.objects.create(
            asset=self.asset,
            assignee=self.assignee,
            holder_snapshot={},
            performed_by=self.user,
            returned_at=timezone.now(),
        )
        self.assertIn("returned", str(a))


# ─────────────────────────────────────────────────────────────────────────────
# perform_transfer service
# ─────────────────────────────────────────────────────────────────────────────

class PerformTransferTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.asset = make_asset()
        self.assignee_a = make_employee_assignee("Md. Karim")
        self.assignee_b = make_employee_assignee("Rina Begum")

    def test_initial_assignment_from_in_stock(self):
        assignment = perform_transfer(self.asset, self.assignee_a, self.user)

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetItem.Status.ASSIGNED)
        self.assertIsNone(assignment.returned_at)
        self.assertEqual(assignment.assignee, self.assignee_a)
        self.assertEqual(assignment.performed_by, self.user)

    def test_snapshot_frozen_in_assignment(self):
        assignment = perform_transfer(self.asset, self.assignee_a, self.user)
        snap = assignment.holder_snapshot
        self.assertEqual(snap["display_name"], "Md. Karim")
        self.assertEqual(snap["assignee_type"], AssigneeType.EMPLOYEE)

    def test_transfer_between_assignees_closes_old(self):
        first = perform_transfer(self.asset, self.assignee_a, self.user)
        second = perform_transfer(self.asset, self.assignee_b, self.user)

        first.refresh_from_db()
        self.assertIsNotNone(first.returned_at)    # old assignment is closed
        self.assertIsNone(second.returned_at)       # new assignment is active
        self.assertEqual(second.assignee, self.assignee_b)

    def test_asset_stays_assigned_after_transfer(self):
        perform_transfer(self.asset, self.assignee_a, self.user)
        perform_transfer(self.asset, self.assignee_b, self.user)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetItem.Status.ASSIGNED)

    def test_only_one_active_assignment_per_asset(self):
        perform_transfer(self.asset, self.assignee_a, self.user)
        perform_transfer(self.asset, self.assignee_b, self.user)
        active = Assignment.objects.filter(asset=self.asset, returned_at__isnull=True)
        self.assertEqual(active.count(), 1)

    def test_raises_for_disposed_asset(self):
        self.asset.status = AssetItem.Status.DISPOSED
        self.asset.save()
        with self.assertRaises(ValidationError) as ctx:
            perform_transfer(self.asset, self.assignee_a, self.user)
        self.assertIn("status", str(ctx.exception).lower())

    def test_raises_for_maintenance_asset(self):
        self.asset.status = AssetItem.Status.MAINTENANCE
        self.asset.save()
        with self.assertRaises(ValidationError):
            perform_transfer(self.asset, self.assignee_a, self.user)

    def test_raises_for_deleted_asset(self):
        self.asset.is_deleted = True
        self.asset.save()
        with self.assertRaises(ValidationError) as ctx:
            perform_transfer(self.asset, self.assignee_a, self.user)
        self.assertIn("deleted", str(ctx.exception).lower())

    def test_raises_for_inactive_assignee(self):
        self.assignee_a.is_active = False
        self.assignee_a.save()
        with self.assertRaises(ValidationError) as ctx:
            perform_transfer(self.asset, self.assignee_a, self.user)
        self.assertIn("inactive", str(ctx.exception).lower())

    def test_with_batch(self):
        year = timezone.now().year
        batch = TransferBatch.objects.create(
            reference=f"TB-{year}-0001",
            performed_by=self.user,
        )
        assignment = perform_transfer(self.asset, self.assignee_a, self.user, batch=batch)
        self.assertEqual(assignment.batch, batch)

    def test_with_notes(self):
        assignment = perform_transfer(
            self.asset, self.assignee_a, self.user, notes="Urgent transfer"
        )
        self.assertEqual(assignment.notes, "Urgent transfer")


# ─────────────────────────────────────────────────────────────────────────────
# return_to_stock service
# ─────────────────────────────────────────────────────────────────────────────

class ReturnToStockTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.asset = make_asset()
        self.assignee = make_employee_assignee()

    def test_return_closes_assignment_and_sets_in_stock(self):
        assignment = perform_transfer(self.asset, self.assignee, self.user)
        return_to_stock(self.asset, self.user)

        self.asset.refresh_from_db()
        assignment.refresh_from_db()

        self.assertEqual(self.asset.status, AssetItem.Status.IN_STOCK)
        self.assertIsNotNone(assignment.returned_at)

    def test_return_raises_if_not_assigned(self):
        with self.assertRaises(ValidationError):
            return_to_stock(self.asset, self.user)


# ─────────────────────────────────────────────────────────────────────────────
# InactiveHolderAlert
# ─────────────────────────────────────────────────────────────────────────────

class InactiveHolderAlertTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.assignee = make_employee_assignee()

    def test_create_open_alert(self):
        alert = InactiveHolderAlert.objects.create(assignee=self.assignee)
        self.assertEqual(alert.status, AlertStatus.OPEN)
        self.assertIsNone(alert.resolved_at)

    def test_resolve_alert(self):
        alert = InactiveHolderAlert.objects.create(assignee=self.assignee)
        alert.resolve(self.user, note="Assets transferred to new officer")
        alert.refresh_from_db()
        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(alert.resolved_by, self.user)
        self.assertIn("transferred", alert.note)

    def test_dismiss_alert(self):
        alert = InactiveHolderAlert.objects.create(assignee=self.assignee)
        alert.dismiss(self.user, note="On leave, not truly inactive")
        alert.refresh_from_db()
        self.assertEqual(alert.status, AlertStatus.DISMISSED)
        self.assertIsNotNone(alert.resolved_at)

    def test_str(self):
        alert = InactiveHolderAlert.objects.create(assignee=self.assignee)
        self.assertIn("OPEN", str(alert))
