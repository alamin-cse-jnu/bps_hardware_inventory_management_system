from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from assets.models import AssetCategory, AssetItem, AssetType

from .models import AuditScan, AuditSession

User = get_user_model()


# ── helpers ───────────────────────────────────────────────────────────────────

def make_user(username="auditor"):
    return User.objects.create_user(username=username, password="pw", is_superuser=True, is_staff=True)


def make_asset(tag="PC-001"):
    cat, _ = AssetCategory.objects.get_or_create(name="Computing")
    atype, _ = AssetType.objects.get_or_create(
        category=cat, name="Laptop", defaults={"spec_schema": []},
    )
    return AssetItem.objects.create(
        asset_tag=tag, asset_type=atype,
        brand="Dell", model_name="Test",
    )


# ── AuditSession ──────────────────────────────────────────────────────────────

class AuditSessionTests(TestCase):

    def test_generate_reference_first(self):
        user = make_user()
        from django.utils import timezone
        year = timezone.now().year
        ref = AuditSession.generate_reference()
        self.assertEqual(ref, f"AUD-{year}-0001")

    def test_generate_reference_increments(self):
        user = make_user()
        from django.utils import timezone
        year = timezone.now().year
        AuditSession.objects.create(
            reference=f"AUD-{year}-0003", performed_by=user,
        )
        ref = AuditSession.generate_reference()
        self.assertEqual(ref, f"AUD-{year}-0004")

    def test_reference_unique(self):
        user = make_user()
        from django.utils import timezone
        year = timezone.now().year
        AuditSession.objects.create(reference=f"AUD-{year}-0001", performed_by=user)
        with self.assertRaises(Exception):
            AuditSession.objects.create(reference=f"AUD-{year}-0001", performed_by=user)

    def test_is_complete_false_by_default(self):
        user = make_user()
        from django.utils import timezone
        year = timezone.now().year
        session = AuditSession.objects.create(
            reference=f"AUD-{year}-0001", performed_by=user,
        )
        self.assertFalse(session.is_complete)

    def test_complete_sets_completed_at(self):
        user = make_user()
        from django.utils import timezone
        year = timezone.now().year
        session = AuditSession.objects.create(
            reference=f"AUD-{year}-0001", performed_by=user,
        )
        session.complete()
        session.refresh_from_db()
        self.assertTrue(session.is_complete)
        self.assertIsNotNone(session.completed_at)

    def test_str(self):
        user = make_user()
        from django.utils import timezone
        year = timezone.now().year
        session = AuditSession.objects.create(
            reference=f"AUD-{year}-0001", performed_by=user,
        )
        self.assertIn("AUD", str(session))


# ── AuditScan ─────────────────────────────────────────────────────────────────

class AuditScanTests(TestCase):

    def setUp(self):
        self.user = make_user()
        from django.utils import timezone
        year = timezone.now().year
        self.session = AuditSession.objects.create(
            reference=f"AUD-{year}-0001", performed_by=self.user,
        )
        self.asset = make_asset()

    def test_create_scan(self):
        scan = AuditScan.objects.create(session=self.session, asset=self.asset)
        self.assertEqual(scan.session, self.session)
        self.assertEqual(scan.asset, self.asset)

    def test_unique_per_session(self):
        AuditScan.objects.create(session=self.session, asset=self.asset)
        with self.assertRaises(Exception):
            AuditScan.objects.create(session=self.session, asset=self.asset)

    def test_same_asset_different_sessions(self):
        from django.utils import timezone
        year = timezone.now().year
        session2 = AuditSession.objects.create(
            reference=f"AUD-{year}-0002", performed_by=self.user,
        )
        AuditScan.objects.create(session=self.session, asset=self.asset)
        scan2 = AuditScan.objects.create(session=session2, asset=self.asset)
        self.assertEqual(scan2.session, session2)

    def test_str(self):
        scan = AuditScan.objects.create(session=self.session, asset=self.asset)
        self.assertIn(self.session.reference, str(scan))
        self.assertIn(self.asset.asset_tag, str(scan))


# ── mobile_scan view ──────────────────────────────────────────────────────────

class MobileScanViewTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.asset = make_asset(tag="LAP-2024-0001")

    def test_returns_200_for_known_tag(self):
        self.client.force_login(self.user)
        url = reverse("qrcodes:mobile_scan", args=[self.asset.asset_tag])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset.asset_tag)

    def test_returns_404_for_unknown_tag(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("qrcodes:mobile_scan", args=["NOTREAL-0000"]))
        self.assertEqual(resp.status_code, 404)

    def test_requires_login(self):
        url = reverse("qrcodes:mobile_scan", args=[self.asset.asset_tag])
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)


# ── qr_download view ──────────────────────────────────────────────────────────

class QRDownloadViewTests(TestCase):

    def test_returns_png(self):
        user = make_user()
        asset = make_asset(tag="LAP-2024-0002")
        self.client.force_login(user)
        url = reverse("qrcodes:qr_download", args=[asset.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
