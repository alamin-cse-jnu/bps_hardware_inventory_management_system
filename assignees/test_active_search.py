"""
Tests for Active Holders search and for locations disappearing from the
assign panel once deactivated.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from assets.models import AssetCategory, AssetItem, AssetType
from assignees.models import (
    Assignee,
    AssigneeType,
    CachedEmployee,
    CachedMP,
    CachedOffice,
)
from assignments.models import Assignment
from locations.models import Building, Location

User = get_user_model()


class HolderFixture(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="holder-tester", password="testpass123!",
            is_superuser=True, is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

        cat, _ = AssetCategory.objects.get_or_create(name="Computing Equipment")
        self.atype, _ = AssetType.objects.get_or_create(
            category=cat, name="Laptop", defaults={"spec_schema": []}
        )
        self.building = Building.objects.create(name="Main Building")
        self._tag = 0

    def give(self, assignee):
        """Give the assignee one asset so it counts as an active holder."""
        self._tag += 1
        asset = AssetItem.objects.create(
            asset_tag=f"AST-{self._tag:04d}", asset_type=self.atype,
            brand="Acme", model_name="M1",
            status=AssetItem.Status.ASSIGNED, created_by=self.user,
        )
        Assignment.objects.create(
            asset=asset, assignee=assignee, performed_by=self.user,
            holder_snapshot=assignee.build_snapshot(),
        )
        return asset

    def employee(self, name, designation="", prp_id=None):
        emp = CachedEmployee.objects.create(
            name_en=name, source="MANUAL",
            designation_en=designation, prp_id=prp_id,
        )
        a = Assignee.objects.create(assignee_type=AssigneeType.EMPLOYEE, employee=emp)
        self.give(a)
        return a

    def mp(self, name, constituency=""):
        rec = CachedMP.objects.create(
            name_en=name, source="MANUAL", constituency=constituency
        )
        a = Assignee.objects.create(assignee_type=AssigneeType.MP, mp=rec)
        self.give(a)
        return a

    def office(self, name):
        rec = CachedOffice.objects.create(name_en=name, source="MANUAL")
        a = Assignee.objects.create(assignee_type=AssigneeType.OFFICE, office=rec)
        self.give(a)
        return a

    def location(self, name, room="", is_active=True):
        loc = Location.objects.create(
            name=name, building=self.building, room=room, is_active=is_active
        )
        loc.sync_assignee()
        a = Assignee.objects.get(assignee_type=AssigneeType.LOCATION, location=loc)
        self.give(a)
        return loc, a

    def get(self, tab, q=None):
        url = reverse("assignees:active_holders") + f"?tab={tab}"
        if q is not None:
            url += f"&q={q}"
        return self.client.get(url)


class ActiveHolderSearchTest(HolderFixture):
    def setUp(self):
        super().setUp()
        self.employee("Abdul Karim", designation="Computer Programmer", prp_id="55501")
        self.employee("Nasrin Sultana", designation="Assistant Director", prp_id="55502")
        self.mp("Rafiqul Islam", constituency="Dhaka-12")
        self.mp("Shirin Akter", constituency="Barisal-4")
        self.office("Information Technology Branch")
        self.office("Protocol Section")
        self.location("Server Room", room="301")
        self.location("Store Room")

    # ── Employees: name / designation / id ───────────────────────────────────

    def test_employee_by_name(self):
        resp = self.get("employees", "Karim")
        self.assertContains(resp, "Abdul Karim")
        self.assertNotContains(resp, "Nasrin Sultana")

    def test_employee_by_designation(self):
        resp = self.get("employees", "Programmer")
        self.assertContains(resp, "Abdul Karim")
        self.assertNotContains(resp, "Nasrin Sultana")

    def test_employee_by_id(self):
        resp = self.get("employees", "55502")
        self.assertContains(resp, "Nasrin Sultana")
        self.assertNotContains(resp, "Abdul Karim")

    def test_employee_search_is_case_insensitive(self):
        self.assertContains(self.get("employees", "kArIm"), "Abdul Karim")

    # ── MPs: name / constituency ─────────────────────────────────────────────

    def test_mp_by_name(self):
        resp = self.get("mps", "Shirin")
        self.assertContains(resp, "Shirin Akter")
        self.assertNotContains(resp, "Rafiqul Islam")

    def test_mp_by_constituency(self):
        resp = self.get("mps", "Dhaka-12")
        self.assertContains(resp, "Rafiqul Islam")
        self.assertNotContains(resp, "Shirin Akter")

    # ── Offices / Locations: name ────────────────────────────────────────────

    def test_office_by_name(self):
        resp = self.get("offices", "Protocol")
        self.assertContains(resp, "Protocol Section")
        self.assertNotContains(resp, "Information Technology Branch")

    def test_location_by_name(self):
        resp = self.get("locations", "Server")
        self.assertContains(resp, "Server Room")
        self.assertNotContains(resp, "Store Room")

    def test_location_by_dimension_shown_in_the_row(self):
        """Rows render full_path, so its parts must be searchable."""
        resp = self.get("locations", "Main Building")
        self.assertContains(resp, "Server Room")

    # ── Cross-tab behaviour ──────────────────────────────────────────────────

    def test_search_does_not_leak_across_types(self):
        """An employee designation term must not surface MPs or offices."""
        resp = self.get("mps", "Programmer")
        self.assertNotContains(resp, "Rafiqul Islam")
        self.assertNotContains(resp, "Shirin Akter")

    def test_counts_reflect_the_search(self):
        resp = self.get("employees", "Karim")
        self.assertEqual(resp.context["counts"]["employees"], 1)
        self.assertEqual(resp.context["counts"]["mps"], 0)

    def test_blank_search_shows_everything(self):
        resp = self.get("employees", "")
        self.assertEqual(resp.context["counts"]["employees"], 2)
        self.assertEqual(resp.context["counts"]["mps"], 2)

    def test_query_is_preserved_in_tab_links(self):
        resp = self.get("employees", "Karim")
        self.assertContains(resp, "?tab=mps&amp;q=Karim")

    def test_no_match_renders_empty_state(self):
        resp = self.get("employees", "zzzznotfound")
        self.assertContains(resp, "No active holders in this category match")

    def test_sl_numbering_restarts_for_filtered_results(self):
        resp = self.get("employees", "Karim")
        self.assertEqual([sl for sl, _ in resp.context["holders"]], [1])

    def test_placeholder_is_tab_specific(self):
        self.assertContains(self.get("mps"), "name or constituency")
        self.assertContains(self.get("employees"), "name, designation or ID")


class InactiveLocationTest(HolderFixture):
    """A deactivated location must not be offerable as an assignment target."""

    def search_panel(self, q=""):
        return self.client.get(
            reverse("assignees:search") + f"?holder_type=LOCATION&q={q}"
        )

    def test_active_location_is_offered(self):
        self.location("Server Room")
        self.assertContains(self.search_panel(), "Server Room")

    def test_deactivating_hides_location_from_assign_panel(self):
        loc, _ = self.location("Server Room")
        self.assertContains(self.search_panel(), "Server Room")

        loc.is_active = False
        loc.save(update_fields=["is_active"])
        loc.sync_assignee()

        self.assertNotContains(self.search_panel(), "Server Room")

    def test_deactivate_view_cascades_to_assignee(self):
        loc = Location.objects.create(name="Old Store", building=self.building)
        loc.sync_assignee()
        assignee = Assignee.objects.get(
            assignee_type=AssigneeType.LOCATION, location=loc
        )
        self.assertTrue(assignee.is_active)

        resp = self.client.post(reverse("locations:delete", args=[loc.pk]))
        self.assertEqual(resp.status_code, 302)

        loc.refresh_from_db()
        assignee.refresh_from_db()
        self.assertFalse(loc.is_active)
        self.assertFalse(assignee.is_active, "Assignee row was left active")

    def test_stale_assignee_row_is_still_filtered_out(self):
        """
        Rows deactivated by a path that skipped the cascade (admin, shell, or
        before sync_assignee existed) must still be excluded by the query.
        """
        loc, assignee = self.location("Ghost Room")
        Location.objects.filter(pk=loc.pk).update(is_active=False)  # no cascade
        assignee.refresh_from_db()
        self.assertTrue(assignee.is_active, "fixture should leave a stale row")

        self.assertNotContains(self.search_panel(), "Ghost Room")

    def test_reactivating_through_the_edit_form_restores_the_assignee(self):
        loc = Location.objects.create(
            name="Back In Service", building=self.building, is_active=False
        )
        loc.sync_assignee()
        self.assertFalse(
            Assignee.objects.get(location=loc).is_active
        )

        resp = self.client.post(reverse("locations:edit", args=[loc.pk]), {
            "name": "Back In Service",
            "building": str(self.building.pk),
            "room": "",
            "is_active": "on",
        })
        self.assertEqual(resp.status_code, 302)

        loc.refresh_from_db()
        self.assertTrue(loc.is_active)
        self.assertTrue(Assignee.objects.get(location=loc).is_active)

    def test_create_still_makes_an_assignee_row(self):
        resp = self.client.post(reverse("locations:create"), {
            "name": "Fresh Room",
            "building": str(self.building.pk),
            "room": "12",
        })
        self.assertEqual(resp.status_code, 302)
        loc = Location.objects.get(name="Fresh Room")
        self.assertTrue(
            Assignee.objects.filter(
                assignee_type=AssigneeType.LOCATION, location=loc, is_active=True
            ).exists()
        )

    def test_inactive_location_still_listed_in_active_holders(self):
        """
        Deactivating a location hides it as a *target*, but assets it already
        holds must stay visible — this page is a record, not a picker.
        """
        loc, _ = self.location("Server Room")
        loc.is_active = False
        loc.save(update_fields=["is_active"])
        loc.sync_assignee()
        self.assertContains(self.get("locations"), "Server Room")
