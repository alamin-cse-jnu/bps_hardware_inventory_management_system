from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from locations.models import Location

from .models import Assignee, AssigneeType, CachedEmployee, CachedMP, CachedOffice, Source

User = get_user_model()


def make_employee(**kwargs) -> CachedEmployee:
    defaults = dict(
        name_en="Test Employee",
        source=Source.MANUAL,
        section_name_en="IT Section",
        branch_name_en="IT Branch",
        wing_name_en="IT Wing",
        office_name_en="Parliament Secretariat",
    )
    defaults.update(kwargs)
    return CachedEmployee.objects.create(**defaults)


def make_mp(**kwargs) -> CachedMP:
    defaults = dict(name_en="Test MP", parliament_no=12, constituency="Dhaka-1", source=Source.MANUAL)
    defaults.update(kwargs)
    return CachedMP.objects.create(**defaults)


def make_office(**kwargs) -> CachedOffice:
    defaults = dict(name_en="IT Department", source=Source.MANUAL)
    defaults.update(kwargs)
    return CachedOffice.objects.create(**defaults)


def make_building() -> Location:
    loc = Location(name="Parliament Bhaban", level_type=Location.LevelType.BUILDING)
    loc.full_clean()
    loc.save()
    return loc


# ─────────────────────────────────────────────────────────────────────────────
# CachedEmployee
# ─────────────────────────────────────────────────────────────────────────────

class CachedEmployeeTests(TestCase):

    def test_create_manual_no_prp_id(self):
        emp = make_employee()
        self.assertEqual(emp.source, Source.MANUAL)
        self.assertIsNone(emp.prp_id)
        self.assertTrue(emp.is_active)

    def test_create_api_with_prp_id(self):
        emp = make_employee(source=Source.PRP_API, prp_id="EMP-001")
        self.assertEqual(emp.prp_id, "EMP-001")
        self.assertEqual(emp.source, Source.PRP_API)

    def test_prp_id_unique_for_api_records(self):
        make_employee(source=Source.PRP_API, prp_id="EMP-DUP")
        with self.assertRaises(Exception):
            make_employee(source=Source.PRP_API, prp_id="EMP-DUP")

    def test_multiple_manual_records_null_prp_id(self):
        make_employee(name_en="Employee A")
        make_employee(name_en="Employee B")
        self.assertEqual(CachedEmployee.objects.filter(prp_id__isnull=True).count(), 2)

    def test_designation_builds_from_section_branch_wing(self):
        emp = make_employee(
            section_name_en="Records Section",
            branch_name_en="Finance Branch",
            wing_name_en="Admin Wing",
        )
        self.assertEqual(emp.designation, "Records Section, Finance Branch, Admin Wing")

    def test_designation_skips_blank_parts(self):
        emp = make_employee(section_name_en="IT Section", branch_name_en="", wing_name_en="IT Wing")
        self.assertEqual(emp.designation, "IT Section, IT Wing")

    def test_designation_empty_when_no_office_details(self):
        emp = CachedEmployee.objects.create(name_en="Bare Employee", source=Source.MANUAL)
        self.assertEqual(emp.designation, "")

    def test_mark_inactive(self):
        emp = make_employee()
        emp.mark_inactive()
        emp.refresh_from_db()
        self.assertFalse(emp.is_active)
        self.assertIsNotNone(emp.inactive_since)

    def test_str(self):
        emp = make_employee(name_en="Md. Karim")
        self.assertIn("Md. Karim", str(emp))


# ─────────────────────────────────────────────────────────────────────────────
# CachedMP
# ─────────────────────────────────────────────────────────────────────────────

class CachedMPTests(TestCase):

    def test_create_mp(self):
        mp = make_mp()
        self.assertEqual(mp.parliament_no, 12)
        self.assertEqual(mp.constituency, "Dhaka-1")
        self.assertTrue(mp.is_active)

    def test_designation_has_constituency(self):
        mp = make_mp(constituency="Chittagong-5", office_details_raw="Speaker's Office")
        self.assertIn("Chittagong-5", mp.designation)

    def test_designation_default_when_no_details(self):
        mp = CachedMP.objects.create(name_en="MP Test", source=Source.MANUAL)
        self.assertEqual(mp.designation, "Member of Parliament")

    def test_mark_inactive(self):
        mp = make_mp()
        mp.mark_inactive()
        mp.refresh_from_db()
        self.assertFalse(mp.is_active)
        self.assertIsNotNone(mp.inactive_since)

    def test_str_includes_parliament_no(self):
        mp = make_mp(name_en="Rina Begum", parliament_no=12)
        self.assertIn("12", str(mp))


# ─────────────────────────────────────────────────────────────────────────────
# CachedOffice
# ─────────────────────────────────────────────────────────────────────────────

class CachedOfficeTests(TestCase):

    def test_create_office(self):
        office = make_office(name_en="Finance Wing", prp_id="OFF-001", source=Source.PRP_API)
        self.assertEqual(office.name_en, "Finance Wing")
        self.assertEqual(office.prp_id, "OFF-001")

    def test_create_manual_office(self):
        office = make_office()
        self.assertEqual(office.source, Source.MANUAL)
        self.assertIsNone(office.prp_id)

    def test_mark_inactive(self):
        office = make_office()
        office.mark_inactive()
        office.refresh_from_db()
        self.assertFalse(office.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# Assignee — clean() validation
# ─────────────────────────────────────────────────────────────────────────────

class AssigneeValidationTests(TestCase):

    def setUp(self):
        self.emp = make_employee()
        self.mp = make_mp()
        self.office = make_office()
        self.location = make_building()

    def _make_assignee(self, **kwargs):
        a = Assignee(**kwargs)
        a.full_clean()
        a.save()
        return a

    def test_employee_assignee_valid(self):
        a = self._make_assignee(assignee_type=AssigneeType.EMPLOYEE, employee=self.emp)
        self.assertEqual(a.display_name, self.emp.name_en)

    def test_mp_assignee_valid(self):
        a = self._make_assignee(assignee_type=AssigneeType.MP, mp=self.mp)
        self.assertEqual(a.display_name, self.mp.name_en)

    def test_office_assignee_valid(self):
        a = self._make_assignee(assignee_type=AssigneeType.OFFICE, office=self.office)
        self.assertEqual(a.display_name, self.office.name_en)

    def test_location_assignee_valid(self):
        a = self._make_assignee(assignee_type=AssigneeType.LOCATION, location=self.location)
        self.assertIn(self.location.name, a.display_name)

    def test_missing_required_fk_raises(self):
        a = Assignee(assignee_type=AssigneeType.EMPLOYEE)  # no employee set
        with self.assertRaises(ValidationError) as ctx:
            a.full_clean()
        self.assertIn("employee", str(ctx.exception))

    def test_wrong_fk_type_raises(self):
        # type=EMPLOYEE but mp is set instead of employee
        a = Assignee(assignee_type=AssigneeType.EMPLOYEE, mp=self.mp)
        with self.assertRaises(ValidationError) as ctx:
            a.full_clean()
        self.assertIn("employee", str(ctx.exception))

    def test_multiple_fks_set_raises(self):
        a = Assignee(
            assignee_type=AssigneeType.EMPLOYEE,
            employee=self.emp,
            mp=self.mp,
        )
        with self.assertRaises(ValidationError) as ctx:
            a.full_clean()
        self.assertIn("mp", str(ctx.exception))


# ─────────────────────────────────────────────────────────────────────────────
# Assignee — display helpers + snapshot
# ─────────────────────────────────────────────────────────────────────────────

class AssigneeSnapshotTests(TestCase):

    def setUp(self):
        self.emp = make_employee(
            name_en="Md. Karim",
            section_name_en="IT Section",
            branch_name_en="IT Branch",
            wing_name_en="IT Wing",
            office_name_en="Parliament Secretariat",
        )
        self.mp = make_mp(name_en="Rina Begum", constituency="Dhaka-1")
        self.office = make_office(name_en="Finance Wing")
        self.building = make_building()

    def test_employee_snapshot(self):
        a = Assignee.objects.create(assignee_type=AssigneeType.EMPLOYEE, employee=self.emp)
        snap = a.build_snapshot()
        self.assertEqual(snap["display_name"], "Md. Karim")
        self.assertEqual(snap["assignee_type"], AssigneeType.EMPLOYEE)
        self.assertIn("IT Section", snap["designation"])
        self.assertEqual(snap["department"], "Parliament Secretariat")
        self.assertEqual(snap["source"], Source.MANUAL)

    def test_mp_snapshot(self):
        a = Assignee.objects.create(assignee_type=AssigneeType.MP, mp=self.mp)
        snap = a.build_snapshot()
        self.assertEqual(snap["display_name"], "Rina Begum")
        self.assertIn("Dhaka-1", snap["designation"])

    def test_office_snapshot(self):
        a = Assignee.objects.create(assignee_type=AssigneeType.OFFICE, office=self.office)
        snap = a.build_snapshot()
        self.assertEqual(snap["display_name"], "Finance Wing")
        self.assertEqual(snap["designation"], "")

    def test_location_snapshot(self):
        a = Assignee.objects.create(assignee_type=AssigneeType.LOCATION, location=self.building)
        snap = a.build_snapshot()
        self.assertIn(self.building.name, snap["display_name"])
        self.assertEqual(snap["source"], "")

    def test_holder_source_manual(self):
        a = Assignee.objects.create(assignee_type=AssigneeType.EMPLOYEE, employee=self.emp)
        self.assertEqual(a.holder_source, Source.MANUAL)

    def test_holder_source_api(self):
        emp_api = make_employee(name_en="API Emp", source=Source.PRP_API, prp_id="E999")
        a = Assignee.objects.create(assignee_type=AssigneeType.EMPLOYEE, employee=emp_api)
        self.assertEqual(a.holder_source, Source.PRP_API)

    def test_holder_source_location_is_empty(self):
        a = Assignee.objects.create(assignee_type=AssigneeType.LOCATION, location=self.building)
        self.assertEqual(a.holder_source, "")
