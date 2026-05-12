"""
Tests for RBAC: viewer_required, it_officer_required, admin_required decorators,
the create_groups management command, and role_context helper.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase
from django.core.exceptions import PermissionDenied

from config.permissions import (
    GROUP_ADMIN,
    GROUP_IT_OFFICER,
    GROUP_VIEWER,
    admin_required,
    is_admin,
    is_it_officer_or_above,
    is_viewer_or_above,
    it_officer_required,
    role_context,
    viewer_required,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(username, **groups):
    u = User.objects.create_user(username=username, password="pass1234567!")
    for g in groups.get("groups", []):
        grp, _ = Group.objects.get_or_create(name=g)
        u.groups.add(grp)
    return u


def _superuser(username="su"):
    return User.objects.create_superuser(username=username, password="pass1234567!")


# ── Predicate tests ───────────────────────────────────────────────────────────

class IsAdminTest(TestCase):
    def test_superuser_is_admin(self):
        self.assertTrue(is_admin(_superuser()))

    def test_admin_group_member_is_admin(self):
        u = _user("a", groups=[GROUP_ADMIN])
        self.assertTrue(is_admin(u))

    def test_it_officer_not_admin(self):
        u = _user("b", groups=[GROUP_IT_OFFICER])
        self.assertFalse(is_admin(u))

    def test_viewer_not_admin(self):
        u = _user("c", groups=[GROUP_VIEWER])
        self.assertFalse(is_admin(u))

    def test_no_group_not_admin(self):
        u = _user("d")
        self.assertFalse(is_admin(u))


class IsITOfficerTest(TestCase):
    def test_superuser_qualifies(self):
        self.assertTrue(is_it_officer_or_above(_superuser()))

    def test_admin_qualifies(self):
        self.assertTrue(is_it_officer_or_above(_user("a", groups=[GROUP_ADMIN])))

    def test_it_officer_qualifies(self):
        self.assertTrue(is_it_officer_or_above(_user("b", groups=[GROUP_IT_OFFICER])))

    def test_viewer_does_not_qualify(self):
        self.assertFalse(is_it_officer_or_above(_user("c", groups=[GROUP_VIEWER])))

    def test_no_group_does_not_qualify(self):
        self.assertFalse(is_it_officer_or_above(_user("d")))


class IsViewerTest(TestCase):
    def test_all_groups_qualify(self):
        for group in [GROUP_ADMIN, GROUP_IT_OFFICER, GROUP_VIEWER]:
            u = _user(f"u_{group}", groups=[group])
            self.assertTrue(is_viewer_or_above(u), f"{group} should qualify as viewer")

    def test_superuser_qualifies(self):
        self.assertTrue(is_viewer_or_above(_superuser()))

    def test_no_group_does_not_qualify(self):
        self.assertFalse(is_viewer_or_above(_user("nogroup")))


# ── Decorator tests ───────────────────────────────────────────────────────────

def _dummy_view(request):
    from django.http import HttpResponse
    return HttpResponse("ok")


class ViewerRequiredDecoratorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = viewer_required(_dummy_view)

    def test_superuser_passes(self):
        req = self.factory.get("/")
        req.user = _superuser("sv")
        resp = self.view(req)
        self.assertEqual(resp.status_code, 200)

    def test_viewer_passes(self):
        req = self.factory.get("/")
        req.user = _user("vv", groups=[GROUP_VIEWER])
        resp = self.view(req)
        self.assertEqual(resp.status_code, 200)

    def test_no_group_raises_403(self):
        req = self.factory.get("/")
        req.user = _user("nogroup2")
        with self.assertRaises(PermissionDenied):
            self.view(req)

    def test_unauthenticated_redirects(self):
        from django.contrib.auth.models import AnonymousUser
        req = self.factory.get("/some/path/")
        req.user = AnonymousUser()
        resp = self.view(req)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])


class ITOfficerRequiredDecoratorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = it_officer_required(_dummy_view)

    def test_it_officer_passes(self):
        req = self.factory.get("/")
        req.user = _user("io", groups=[GROUP_IT_OFFICER])
        resp = self.view(req)
        self.assertEqual(resp.status_code, 200)

    def test_viewer_blocked(self):
        req = self.factory.get("/")
        req.user = _user("vb", groups=[GROUP_VIEWER])
        with self.assertRaises(PermissionDenied):
            self.view(req)

    def test_no_group_blocked(self):
        req = self.factory.get("/")
        req.user = _user("nb")
        with self.assertRaises(PermissionDenied):
            self.view(req)


class AdminRequiredDecoratorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = admin_required(_dummy_view)

    def test_admin_group_passes(self):
        req = self.factory.get("/")
        req.user = _user("ag", groups=[GROUP_ADMIN])
        resp = self.view(req)
        self.assertEqual(resp.status_code, 200)

    def test_it_officer_blocked(self):
        req = self.factory.get("/")
        req.user = _user("iob", groups=[GROUP_IT_OFFICER])
        with self.assertRaises(PermissionDenied):
            self.view(req)


# ── role_context tests ────────────────────────────────────────────────────────

class RoleContextTest(TestCase):
    def test_superuser_all_true(self):
        ctx = role_context(_superuser("rsu"))
        self.assertTrue(ctx["user_is_admin"])
        self.assertTrue(ctx["user_is_it_officer"])
        self.assertTrue(ctx["user_is_viewer"])

    def test_viewer_only_viewer_flag(self):
        ctx = role_context(_user("rv", groups=[GROUP_VIEWER]))
        self.assertFalse(ctx["user_is_admin"])
        self.assertFalse(ctx["user_is_it_officer"])
        self.assertTrue(ctx["user_is_viewer"])

    def test_no_group_all_false(self):
        ctx = role_context(_user("rn"))
        self.assertFalse(ctx["user_is_admin"])
        self.assertFalse(ctx["user_is_it_officer"])
        self.assertFalse(ctx["user_is_viewer"])


# ── create_groups command tests ───────────────────────────────────────────────

class CreateGroupsCommandTest(TestCase):
    def test_creates_all_three_groups(self):
        Group.objects.all().delete()
        call_command("create_groups", verbosity=0)
        names = set(Group.objects.values_list("name", flat=True))
        self.assertIn(GROUP_ADMIN, names)
        self.assertIn(GROUP_IT_OFFICER, names)
        self.assertIn(GROUP_VIEWER, names)

    def test_idempotent(self):
        call_command("create_groups", verbosity=0)
        call_command("create_groups", verbosity=0)  # second run should not raise
        self.assertEqual(Group.objects.filter(name=GROUP_ADMIN).count(), 1)

    def test_viewer_has_fewer_permissions_than_it_officer(self):
        call_command("create_groups", verbosity=0)
        viewer = Group.objects.get(name=GROUP_VIEWER)
        officer = Group.objects.get(name=GROUP_IT_OFFICER)
        self.assertLess(
            viewer.permissions.count(),
            officer.permissions.count(),
        )


# ── HTTP integration: 403 page ────────────────────────────────────────────────

class ForbiddenPageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="forbuser", password="pass123456!")
        self.client.login(username="forbuser", password="pass123456!")

    def test_viewer_protected_view_returns_403(self):
        # A user with no group hits a viewer_required view → 403
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 403)

    def test_it_officer_protected_view_returns_403_for_viewer(self):
        Group.objects.get_or_create(name=GROUP_VIEWER)
        self.user.groups.add(Group.objects.get(name=GROUP_VIEWER))
        # assign_panel requires IT Officer
        from assets.models import AssetCategory, AssetItem, AssetType
        cat, _ = AssetCategory.objects.get_or_create(name="TestCat403")
        atype, _ = AssetType.objects.get_or_create(
            category=cat, name="TestType403", defaults={"spec_schema": []}
        )
        asset = AssetItem.objects.create(
            asset_tag="PERM-001", asset_type=atype, brand="X", model_name="Y"
        )
        resp = self.client.get(f"/assignments/{asset.pk}/assign/")
        self.assertEqual(resp.status_code, 403)
