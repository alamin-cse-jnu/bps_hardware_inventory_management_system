from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from assignees.models import (
    Assignee,
    AssigneeType,
    CachedEmployee,
    CachedMP,
    CachedOffice,
    Source,
)
from assignments.models import AlertStatus, OfficeChangeAlert

from .models import SyncLog
from .services import _sync_employees, _sync_mps, _sync_offices, run_full_sync

User = get_user_model()

# ── Sample API records ────────────────────────────────────────────────────────

EMPLOYEE = {
    "prpId": "EMP001",
    "nameEn": "John Doe",
    "nameBn": "জন ডো",
    "mobile": "01700000001",
    "telephone": "",
    "gender": "Male",
    "photo": "",
    "status": "Active",
    "officeDetails": {
        "wingId": 1, "wingNameEn": "Admin Wing", "wingNameBn": "",
        "branchId": 2, "branchNameEn": "IT Branch", "branchNameBn": "",
        "sectionId": 3, "sectionNameEn": "Software Section", "sectionNameBn": "",
        "unitId": None, "unitNameEn": "", "unitNameBn": "",
        "officeId": 10, "officeNameEn": "Parliament Secretariat", "officeNameBn": "",
    },
}

MP = {
    "prpId": "MP001",
    "nameEn": "Jane Smith",
    "nameBn": "জেন স্মিথ",
    "parliamentNo": 12,
    "constituency": "Dhaka-1",
    "mobile": "01700000002",
    "telephone": "",
    "gender": "Female",
    "photo": "",
    "status": "Active",
    "officeDetails": "MP Office",
}

OFFICE = {
    "id": "OFF001",
    "nameEn": "IT Division",
    "nameBn": "",
    "parentId": None,
    "isAbstractOffice": False,
}


# ── SyncLog model ─────────────────────────────────────────────────────────────

class SyncLogModelTests(TestCase):
    def test_total_properties(self):
        log = SyncLog(
            employees_added=1, employees_updated=2, employees_flagged=3,
            mps_added=4, mps_updated=5, mps_flagged=6,
            offices_added=7, offices_updated=8, offices_flagged=9,
        )
        self.assertEqual(log.total_added, 12)
        self.assertEqual(log.total_updated, 15)
        self.assertEqual(log.total_flagged, 18)

    def test_duration_none_when_incomplete(self):
        log = SyncLog(completed_at=None)
        self.assertIsNone(log.duration_seconds)

    def test_duration_computed_when_complete(self):
        from django.utils import timezone
        import datetime
        log = SyncLog.objects.create()
        log.completed_at = log.started_at + datetime.timedelta(seconds=42)
        self.assertAlmostEqual(log.duration_seconds, 42, delta=1)

    def test_str_includes_status(self):
        log = SyncLog.objects.create(status=SyncLog.Status.SUCCESS)
        self.assertIn("SUCCESS", str(log))

    def test_default_status_is_running(self):
        log = SyncLog.objects.create()
        self.assertEqual(log.status, SyncLog.Status.RUNNING)


# ── Employee sync ─────────────────────────────────────────────────────────────

class SyncEmployeesTests(TestCase):
    def test_creates_new_employee(self):
        log = SyncLog.objects.create()
        _sync_employees([EMPLOYEE], log)
        self.assertEqual(log.employees_added, 1)
        self.assertEqual(log.employees_updated, 0)
        emp = CachedEmployee.objects.get(prp_id="EMP001")
        self.assertEqual(emp.name_en, "John Doe")
        self.assertEqual(emp.branch_name_en, "IT Branch")
        self.assertEqual(emp.office_name_en, "Parliament Secretariat")
        self.assertTrue(emp.is_active)

    def test_updates_existing_employee(self):
        CachedEmployee.objects.create(
            prp_id="EMP001", source=Source.PRP_API, name_en="Old Name",
        )
        log = SyncLog.objects.create()
        _sync_employees([EMPLOYEE], log)
        self.assertEqual(log.employees_added, 0)
        self.assertEqual(log.employees_updated, 1)
        self.assertEqual(CachedEmployee.objects.get(prp_id="EMP001").name_en, "John Doe")

    def test_flags_employee_absent_from_api(self):
        CachedEmployee.objects.create(
            prp_id="GONE001", source=Source.PRP_API, name_en="Gone", is_active=True,
        )
        log = SyncLog.objects.create()
        _sync_employees([], log)
        self.assertEqual(log.employees_flagged, 1)
        self.assertFalse(CachedEmployee.objects.get(prp_id="GONE001").is_active)

    def test_does_not_flag_manual_records(self):
        CachedEmployee.objects.create(
            prp_id=None, source=Source.MANUAL, name_en="Manual Person", is_active=True,
        )
        log = SyncLog.objects.create()
        _sync_employees([], log)
        self.assertEqual(log.employees_flagged, 0)
        self.assertTrue(CachedEmployee.objects.get(source=Source.MANUAL).is_active)

    def test_skips_records_without_prp_id(self):
        log = SyncLog.objects.create()
        _sync_employees([{"nameEn": "No ID"}], log)
        self.assertEqual(log.employees_added, 0)

    def test_already_inactive_not_double_counted(self):
        CachedEmployee.objects.create(
            prp_id="ALREADY_GONE", source=Source.PRP_API,
            name_en="Already Gone", is_active=False,
        )
        log = SyncLog.objects.create()
        _sync_employees([], log)
        # is_active=False employees are excluded from the flagging query
        self.assertEqual(log.employees_flagged, 0)


# ── MP sync ───────────────────────────────────────────────────────────────────

class SyncMPsTests(TestCase):
    def test_creates_new_mp(self):
        log = SyncLog.objects.create()
        _sync_mps([MP], log)
        self.assertEqual(log.mps_added, 1)
        mp = CachedMP.objects.get(prp_id="MP001")
        self.assertEqual(mp.name_en, "Jane Smith")
        self.assertEqual(mp.parliament_no, 12)
        self.assertEqual(mp.constituency, "Dhaka-1")

    def test_updates_existing_mp(self):
        CachedMP.objects.create(
            prp_id="MP001", source=Source.PRP_API, name_en="Old MP Name",
        )
        log = SyncLog.objects.create()
        _sync_mps([MP], log)
        self.assertEqual(log.mps_updated, 1)
        self.assertEqual(CachedMP.objects.get(prp_id="MP001").name_en, "Jane Smith")

    def test_flags_mp_absent_from_api(self):
        CachedMP.objects.create(
            prp_id="GONE_MP", source=Source.PRP_API, name_en="Gone MP", is_active=True,
        )
        log = SyncLog.objects.create()
        _sync_mps([], log)
        self.assertEqual(log.mps_flagged, 1)
        self.assertFalse(CachedMP.objects.get(prp_id="GONE_MP").is_active)

    def test_does_not_flag_manual_mp(self):
        CachedMP.objects.create(
            prp_id=None, source=Source.MANUAL, name_en="Manual MP", is_active=True,
        )
        log = SyncLog.objects.create()
        _sync_mps([], log)
        self.assertEqual(log.mps_flagged, 0)


# ── Office sync ───────────────────────────────────────────────────────────────

class SyncOfficesTests(TestCase):
    def test_creates_new_office(self):
        log = SyncLog.objects.create()
        _sync_offices([OFFICE], log)
        self.assertEqual(log.offices_added, 1)
        office = CachedOffice.objects.get(prp_id="OFF001")
        self.assertEqual(office.name_en, "IT Division")
        self.assertFalse(office.is_abstract)

    def test_flags_office_absent_from_api(self):
        CachedOffice.objects.create(
            prp_id="GONE_OFF", source=Source.PRP_API, name_en="Gone Office", is_active=True,
        )
        log = SyncLog.objects.create()
        _sync_offices([], log)
        self.assertEqual(log.offices_flagged, 1)
        self.assertFalse(CachedOffice.objects.get(prp_id="GONE_OFF").is_active)


# ── Full sync orchestration ───────────────────────────────────────────────────

class RunFullSyncTests(TestCase):
    @patch("sync_prp.services.PRPApiClient")
    def test_success_when_all_endpoints_succeed(self, MockClient):
        mc = MockClient.return_value
        mc.get_employees.return_value = [EMPLOYEE]
        mc.get_mps.return_value = [MP]
        mc.get_offices.return_value = [OFFICE]

        log = run_full_sync()
        self.assertEqual(log.status, SyncLog.Status.SUCCESS)
        self.assertIsNotNone(log.completed_at)
        self.assertEqual(log.total_added, 3)

    @patch("sync_prp.services.PRPApiClient")
    def test_partial_when_one_endpoint_fails(self, MockClient):
        mc = MockClient.return_value
        mc.get_employees.side_effect = Exception("timeout")
        mc.get_mps.return_value = []
        mc.get_offices.return_value = []

        log = run_full_sync()
        self.assertEqual(log.status, SyncLog.Status.PARTIAL)
        self.assertIn("employees", log.error_message)

    @patch("sync_prp.services.PRPApiClient")
    def test_failed_when_all_endpoints_fail(self, MockClient):
        mc = MockClient.return_value
        mc.get_employees.side_effect = Exception("err")
        mc.get_mps.side_effect = Exception("err")
        mc.get_offices.side_effect = Exception("err")

        log = run_full_sync()
        self.assertEqual(log.status, SyncLog.Status.FAILED)
        self.assertNotEqual(log.error_message, "")

    @patch("sync_prp.services.PRPApiClient")
    def test_completed_at_always_set(self, MockClient):
        mc = MockClient.return_value
        mc.get_employees.side_effect = Exception("err")
        mc.get_mps.side_effect = Exception("err")
        mc.get_offices.side_effect = Exception("err")

        log = run_full_sync()
        self.assertIsNotNone(log.completed_at)

    @patch("sync_prp.services.PRPApiClient")
    def test_triggered_by_stored(self, MockClient):
        mc = MockClient.return_value
        mc.get_employees.return_value = []
        mc.get_mps.return_value = []
        mc.get_offices.return_value = []

        user = User.objects.create_user(username="tester", password="pass")
        log = run_full_sync(triggered_by=user)
        self.assertEqual(log.triggered_by, user)


# ── Office change detection ───────────────────────────────────────────────────

class OfficeChangeDetectionTests(TestCase):
    """
    A PRP employee moving between offices while still holding assets raises an
    OfficeChangeAlert. Like the inactive-holder flag, nothing is auto-returned.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="syncer", password="pw12345678")

    def _seed_employee(self, **placement):
        """Create EMP001 as it stood before the sync run."""
        defaults = {
            "wing_id": "1", "wing_name_en": "Admin Wing",
            "branch_id": "2", "branch_name_en": "IT Branch",
            "section_id": "3", "section_name_en": "Software Section",
            "unit_id": "", "office_id": "10",
            "office_name_en": "Parliament Secretariat",
        }
        defaults.update(placement)
        return CachedEmployee.objects.create(
            prp_id="EMP001", source=Source.PRP_API, name_en="John Doe", **defaults,
        )

    def _give_asset(self, emp):
        """Put one active assignment on the employee."""
        from assets.models import AssetCategory, AssetItem, AssetType
        from assignments.models import Assignment

        assignee, _ = Assignee.objects.get_or_create(
            assignee_type=AssigneeType.EMPLOYEE, employee=emp,
        )
        cat, _ = AssetCategory.objects.get_or_create(name="Computing")
        atype, _ = AssetType.objects.get_or_create(
            category=cat, name="Laptop", defaults={"spec_schema": []},
        )
        asset = AssetItem.objects.create(
            asset_tag="PC-2024-9001", asset_type=atype, brand="Dell",
            model_name="Latitude", status=AssetItem.Status.ASSIGNED,
        )
        Assignment.objects.create(
            asset=asset, assignee=assignee, holder_snapshot=assignee.build_snapshot(),
            performed_by=self.user,
        )
        return assignee

    @staticmethod
    def _moved_record(**office_overrides):
        rec = deepcopy(EMPLOYEE)
        rec["officeDetails"].update(office_overrides)
        return rec

    def test_raises_alert_when_holder_moves_office(self):
        emp = self._seed_employee()
        assignee = self._give_asset(emp)

        _sync_employees([self._moved_record(branchId=7, branchNameEn="Finance Branch")],
                        SyncLog.objects.create())

        alert = OfficeChangeAlert.objects.get(assignee=assignee)
        self.assertEqual(alert.status, AlertStatus.OPEN)
        self.assertEqual(alert.old_placement["branch_name_en"], "IT Branch")
        self.assertEqual(alert.new_placement["branch_name_en"], "Finance Branch")

    def test_no_alert_when_holder_has_no_assets(self):
        self._seed_employee()
        _sync_employees([self._moved_record(branchId=7, branchNameEn="Finance Branch")],
                        SyncLog.objects.create())
        self.assertEqual(OfficeChangeAlert.objects.count(), 0)

    def test_no_alert_when_placement_unchanged(self):
        emp = self._seed_employee()
        self._give_asset(emp)
        _sync_employees([EMPLOYEE], SyncLog.objects.create())
        self.assertEqual(OfficeChangeAlert.objects.count(), 0)

    def test_no_alert_for_rename_only(self):
        """Same office ids, new label on the PRP side — not a move."""
        emp = self._seed_employee()
        self._give_asset(emp)
        _sync_employees([self._moved_record(branchNameEn="ICT Branch")],
                        SyncLog.objects.create())
        self.assertEqual(OfficeChangeAlert.objects.count(), 0)
        self.assertEqual(
            CachedEmployee.objects.get(prp_id="EMP001").branch_name_en, "ICT Branch",
        )

    def test_no_alert_for_first_sight_of_employee(self):
        """A newly created employee has no 'before' placement to move from."""
        _sync_employees([EMPLOYEE], SyncLog.objects.create())
        self.assertEqual(OfficeChangeAlert.objects.count(), 0)

    def test_second_move_updates_open_alert_keeping_origin(self):
        emp = self._seed_employee()
        assignee = self._give_asset(emp)

        _sync_employees([self._moved_record(branchId=7, branchNameEn="Finance Branch")],
                        SyncLog.objects.create())
        _sync_employees([self._moved_record(branchId=8, branchNameEn="Audit Branch")],
                        SyncLog.objects.create())

        self.assertEqual(OfficeChangeAlert.objects.count(), 1)
        alert = OfficeChangeAlert.objects.get(assignee=assignee)
        # Origin stays where the assets were last confirmed; destination advances.
        self.assertEqual(alert.old_placement["branch_name_en"], "IT Branch")
        self.assertEqual(alert.new_placement["branch_name_en"], "Audit Branch")

    def test_move_after_resolution_raises_a_new_alert(self):
        emp = self._seed_employee()
        assignee = self._give_asset(emp)

        _sync_employees([self._moved_record(branchId=7, branchNameEn="Finance Branch")],
                        SyncLog.objects.create())
        OfficeChangeAlert.objects.get(assignee=assignee).resolve(self.user)

        _sync_employees([self._moved_record(branchId=8, branchNameEn="Audit Branch")],
                        SyncLog.objects.create())

        self.assertEqual(OfficeChangeAlert.objects.count(), 2)
        self.assertEqual(
            OfficeChangeAlert.objects.filter(status=AlertStatus.OPEN).count(), 1,
        )

    def test_alert_does_not_return_the_asset(self):
        """Architectural decision #9 — the flag never moves an asset."""
        from assets.models import AssetItem
        from assignments.models import Assignment

        emp = self._seed_employee()
        self._give_asset(emp)
        _sync_employees([self._moved_record(sectionId=99, sectionNameEn="Payroll Section")],
                        SyncLog.objects.create())

        asset = AssetItem.objects.get(asset_tag="PC-2024-9001")
        self.assertEqual(asset.status, AssetItem.Status.ASSIGNED)
        self.assertTrue(
            Assignment.objects.filter(asset=asset, returned_at__isnull=True).exists()
        )
