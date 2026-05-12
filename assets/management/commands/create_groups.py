"""
Management command: create_groups

Creates the three RBAC groups (Admin, IT Officer, Viewer) with appropriate
Django model permissions pre-assigned. Safe to run multiple times.

Usage:
    python manage.py create_groups
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


def _perms(*codenames):
    return list(
        Permission.objects.filter(codename__in=codenames)
    )


class Command(BaseCommand):
    help = "Create Admin, IT Officer, and Viewer RBAC groups"

    def handle(self, *args, **options):
        self._create_admin()
        self._create_it_officer()
        self._create_viewer()
        self.stdout.write(self.style.SUCCESS(
            "RBAC groups created/verified: Admin | IT Officer | Viewer"
        ))

    def _create_admin(self):
        group, created = Group.objects.get_or_create(name="Admin")
        # Admin gets all permissions — Django admin handles the rest via is_staff
        all_perms = Permission.objects.all()
        group.permissions.set(all_perms)
        verb = "Created" if created else "Updated"
        self.stdout.write(f"  {verb}: Admin ({all_perms.count()} permissions)")

    def _create_it_officer(self):
        group, created = Group.objects.get_or_create(name="IT Officer")
        # Operational permissions: view everything + add/change assets, assignments, lifecycle
        codenames = [
            # assets
            "view_assetcategory", "view_assettype", "view_assetitem", "view_assetcomponent",
            "add_assetitem", "change_assetitem",
            # assignees
            "view_cachedemployee", "view_cachedmp", "view_cachedoffice",
            "view_assignee",
            "add_cachedemployee", "change_cachedemployee",
            "add_cachedmp", "change_cachedmp",
            "add_cachedoffice", "change_cachedoffice",
            "add_assignee", "change_assignee",
            # assignments
            "view_assignment", "view_transferbatch", "view_inactiveholderalert",
            "add_assignment", "add_transferbatch",
            "change_inactiveholderalert",
            # lifecycle
            "view_lifecycleevent", "add_lifecycleevent",
            # locations
            "view_location",
            # qrcodes
            "view_auditsession", "view_auditscan",
            "add_auditsession", "add_auditscan",
            # sync_prp
            "view_synclog",
        ]
        perms = _perms(*codenames)
        group.permissions.set(perms)
        verb = "Created" if created else "Updated"
        self.stdout.write(f"  {verb}: IT Officer ({len(perms)} permissions)")

    def _create_viewer(self):
        group, created = Group.objects.get_or_create(name="Viewer")
        # Read-only: view everything
        codenames = [
            "view_assetcategory", "view_assettype", "view_assetitem", "view_assetcomponent",
            "view_cachedemployee", "view_cachedmp", "view_cachedoffice", "view_assignee",
            "view_assignment", "view_transferbatch", "view_inactiveholderalert",
            "view_lifecycleevent",
            "view_location",
            "view_auditsession", "view_auditscan",
            "view_synclog",
        ]
        perms = _perms(*codenames)
        group.permissions.set(perms)
        verb = "Created" if created else "Updated"
        self.stdout.write(f"  {verb}: Viewer ({len(perms)} permissions)")
