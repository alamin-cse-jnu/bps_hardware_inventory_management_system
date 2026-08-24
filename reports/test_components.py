"""
Tests for the component catalogue and the Component Purchases report (Phase 13).

Covers the pieces that can silently go wrong:
  * master data — the mapping that switches ``has_components`` on, and the
    delete guard that protects a part already fitted somewhere
  * component validation — capacity, unit, serial and cost rules
  * report filtering — the two date bases, and vendor / component / status
  * summary totals — vendor-wise and date-wise, including uncosted rows
  * the panel and both downloads over HTTP
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assets.models import AssetCategory, AssetComponent, AssetItem, AssetType, Vendor
from catalogue.models import ComponentType
from lifecycle.services import add_component, remove_component, swap_component
from reports import components as report

User = get_user_model()

XLSX_MAGIC = b"PK"


class ComponentFixture(TestCase):
    """One PC Set that takes RAM and Storage, plus a router that takes SFPs."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="component-tester", password="testpass123!",
            is_superuser=True, is_staff=True,
        )
        self.category = AssetCategory.objects.create(name="Computers")
        self.pc_type = AssetType.objects.create(
            category=self.category, name="PC Set", spec_schema=[],
        )
        self.router_type = AssetType.objects.create(
            category=self.category, name="Router", spec_schema=[],
        )

        # The backfill migration seeds these codes, so configure the seeded rows
        # rather than creating duplicates — ``name`` and ``code`` are unique.
        def part(code, **fields):
            row, _ = ComponentType.objects.update_or_create(code=code, defaults=fields)
            return row

        self.ram = part(
            "ram", name="RAM", units=["GB"], default_unit="GB",
            capacity_required=True, order=0,
        )
        self.storage = part(
            "storage-drive", name="Storage", units=["GB", "TB"], default_unit="GB",
            capacity_required=True, order=1,
        )
        self.sfp = part("sfp", name="SFP Module", capacity_required=False, order=2)
        self.keyboard = part(
            "keyboard", name="Keyboard", units=[], capacity_required=False, order=3,
        )

        # Mapping is what turns the Sub Asset's components panel on.
        self.ram.applies_to.add(self.pc_type)
        self.storage.applies_to.add(self.pc_type)
        self.keyboard.applies_to.add(self.pc_type)
        self.sfp.applies_to.add(self.router_type)
        # Left deliberately unmapped: an allow-list with nothing on it means the
        # part is offered on no asset at all.
        self.unmapped = ComponentType.objects.create(
            name="Thermal Paste", code="thermal-paste", capacity_required=False,
        )
        self.pc_type.refresh_from_db()
        self.router_type.refresh_from_db()

        self.vendor_a = Vendor.objects.create(name="Star Tech")
        self.vendor_b = Vendor.objects.create(name="Ryans Computers")

        self.asset = AssetItem.objects.create(
            asset_tag="PC-0001", asset_type=self.pc_type,
            brand="Dell", model_name="OptiPlex 7010",
        )

    def fit(self, ctype=None, **kwargs):
        """Fit a part, filling in whatever the test does not care about."""
        defaults = {
            "capacity": Decimal("16"),
            "unit": "GB",
            "cost": Decimal("10000.00"),
            "vendor": self.vendor_a,
            "purchase_date": datetime.date(2026, 3, 12),
        }
        defaults.update(kwargs)
        asset = defaults.pop("asset", self.asset)
        return add_component(
            asset, "", defaults.pop("brand", "Kingston"),
            defaults.pop("model", "Fury"), defaults.pop("serial", ""),
            self.user, ctype=ctype or self.ram, **defaults,
        ).component


# ── Master data ───────────────────────────────────────────────────────────────

class ComponentTypeTests(ComponentFixture):
    def test_mapping_enables_components_on_the_sub_asset(self):
        spare = AssetType.objects.create(
            category=self.category, name="Server", spec_schema=[],
        )
        self.assertFalse(spare.has_components)
        self.ram.applies_to.add(spare)
        spare.refresh_from_db()
        self.assertTrue(spare.has_components)

    def test_unmapping_does_not_disable_components(self):
        # Another part may still be mapped, so removing one is no proof.
        self.ram.applies_to.remove(self.pc_type)
        self.pc_type.refresh_from_db()
        self.assertTrue(self.pc_type.has_components)

    def test_unmapped_part_is_offered_nowhere(self):
        # applies_to is an allow-list, not an exclusion list: nothing selected
        # means the part appears on no asset at all.
        self.assertFalse(self.unmapped.available_for(self.pc_type))
        self.assertFalse(self.unmapped.available_for(self.router_type))

    def test_mapped_part_is_only_available_where_mapped(self):
        self.assertTrue(self.ram.available_for(self.pc_type))
        self.assertFalse(self.ram.available_for(self.router_type))

    def test_default_unit_must_be_one_of_the_units(self):
        bad = ComponentType(name="Bad", code="bad", units=["GB"], default_unit="TB")
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_save_maps_sub_assets_and_enables_them(self):
        self.client.force_login(self.user)
        spare = AssetType.objects.create(
            category=self.category, name="Switch", spec_schema=[],
        )
        resp = self.client.post(reverse("catalogue:component_save"), {
            "name": "Cooling Fan",
            "units": "W",
            "default_unit": "W",
            "capacity_required": "on",
            "applies_to": [str(spare.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        created = ComponentType.objects.get(name="Cooling Fan")
        self.assertEqual(created.code, "cooling-fan")
        self.assertEqual(created.units, ["W"])
        spare.refresh_from_db()
        self.assertTrue(spare.has_components)

    def test_save_with_no_sub_asset_selected_warns(self):
        from django.contrib.messages import get_messages

        self.client.force_login(self.user)
        resp = self.client.post(reverse("catalogue:component_save"), {
            "name": "Cooling Fan", "units": "W", "default_unit": "W",
        }, follow=True)
        created = ComponentType.objects.get(name="Cooling Fan")
        self.assertEqual(list(created.applies_to.all()), [])
        levels = [(m.level_tag, m.message) for m in get_messages(resp.wsgi_request)]
        self.assertTrue(
            any(tag == "warning" and "will not appear on any asset" in msg
                for tag, msg in levels),
            f"expected an unmapped-part warning, got {levels}",
        )

    def test_save_rejects_a_default_unit_outside_the_unit_list(self):
        self.client.force_login(self.user)
        self.client.post(reverse("catalogue:component_save"), {
            "name": "Riser Card", "units": "Wh", "default_unit": "mAh",
        })
        self.assertFalse(ComponentType.objects.filter(name="Riser Card").exists())

    def test_rename_keeps_the_code_so_fitted_parts_stay_linked(self):
        self.client.force_login(self.user)
        component = self.fit()
        self.client.post(reverse("catalogue:component_save"), {
            "pk": str(self.ram.pk), "name": "System Memory", "units": "GB",
            "default_unit": "GB", "capacity_required": "on",
        })
        self.ram.refresh_from_db()
        component.refresh_from_db()
        self.assertEqual(self.ram.name, "System Memory")
        self.assertEqual(self.ram.code, "ram")
        self.assertEqual(component.ctype_id, self.ram.pk)

    def test_delete_is_refused_while_a_part_is_fitted(self):
        self.client.force_login(self.user)
        self.fit()
        self.client.post(reverse("catalogue:component_delete", args=[self.ram.pk]))
        self.assertTrue(ComponentType.objects.filter(pk=self.ram.pk).exists())

    def test_delete_is_allowed_when_unused(self):
        self.client.force_login(self.user)
        self.client.post(reverse("catalogue:component_delete", args=[self.keyboard.pk]))
        self.assertFalse(ComponentType.objects.filter(pk=self.keyboard.pk).exists())


# ── Component validation ──────────────────────────────────────────────────────

class ComponentValidationTests(ComponentFixture):
    def test_sized_part_requires_a_capacity(self):
        with self.assertRaises(ValidationError):
            self.fit(capacity=None)

    def test_unit_must_be_one_the_part_uses(self):
        with self.assertRaises(ValidationError):
            self.fit(unit="TB")

    def test_second_unit_of_a_multi_unit_part_is_accepted(self):
        component = self.fit(ctype=self.storage, capacity=Decimal("2"), unit="TB")
        self.assertEqual(component.capacity_display, "2 TB")

    def test_capacity_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.fit(capacity=Decimal("0"))

    def test_cost_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self.fit(cost=Decimal("-1"))

    def test_part_not_offered_for_this_sub_asset_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.fit(ctype=self.sfp)

    def test_unsized_part_needs_no_capacity(self):
        component = self.fit(ctype=self.keyboard, capacity=None, unit="", cost=None)
        self.assertEqual(component.capacity_display, "")
        self.assertEqual(component.label, "Keyboard")

    def test_serial_required_part_rejects_a_blank_serial(self):
        self.keyboard.serial_required = True
        self.keyboard.save(update_fields=["serial_required"])
        with self.assertRaises(ValidationError):
            self.fit(ctype=self.keyboard, capacity=None, unit="", serial="")

    def test_legacy_column_is_filled_from_the_master_data_code(self):
        component = self.fit()
        self.assertEqual(component.component_type, AssetComponent.ComponentType.RAM)

    def test_part_with_no_matching_enum_member_falls_back_to_other(self):
        odd = self.unmapped
        odd.applies_to.add(self.pc_type)
        component = self.fit(ctype=odd, capacity=None, unit="", cost=None)
        self.assertEqual(component.component_type, AssetComponent.ComponentType.OTHER)
        self.assertEqual(component.label, "Thermal Paste")

    def test_capacity_display_trims_trailing_zeros(self):
        self.assertEqual(self.fit(capacity=Decimal("16.00")).capacity_display, "16 GB")

    def test_legacy_row_without_master_data_still_names_itself(self):
        legacy = AssetComponent.objects.create(
            parent_asset=self.asset,
            component_type=AssetComponent.ComponentType.MONITOR,
        )
        self.assertEqual(legacy.label, "Monitor")

    def test_rejected_replacement_leaves_the_old_part_installed(self):
        old = self.fit()
        with self.assertRaises(ValidationError):
            swap_component(
                self.asset, old, "", "Kingston", "Fury", "", self.user,
                ctype=self.ram, capacity=None, unit="GB",
            )
        old.refresh_from_db()
        self.assertTrue(old.is_active)
        self.assertIsNone(old.removed_at)

    def test_replacement_carries_its_own_purchase_details(self):
        old = self.fit(cost=Decimal("5000.00"))
        event = swap_component(
            self.asset, old, "", "Corsair", "Vengeance", "SN-9", self.user,
            ctype=self.ram, capacity=Decimal("32"), unit="GB",
            cost=Decimal("18000.00"), vendor=self.vendor_b,
            purchase_date=datetime.date(2026, 5, 1),
        )
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertEqual(event.component.cost, Decimal("18000.00"))
        self.assertEqual(event.component.vendor, self.vendor_b)
        self.assertEqual(event.component.capacity_display, "32 GB")


# ── Report query + summary ────────────────────────────────────────────────────

class ComponentReportTests(ComponentFixture):
    def setUp(self):
        super().setUp()
        self.march = self.fit(
            cost=Decimal("10000.00"), vendor=self.vendor_a,
            purchase_date=datetime.date(2026, 3, 12),
        )
        self.april = self.fit(
            ctype=self.storage, capacity=Decimal("1"), unit="TB",
            cost=Decimal("7000.00"), vendor=self.vendor_b,
            purchase_date=datetime.date(2026, 4, 2),
        )
        self.undated = self.fit(
            ctype=self.keyboard, capacity=None, unit="",
            cost=None, vendor=None, purchase_date=None,
        )

    def rows(self, **kwargs):
        return list(report.component_queryset(**kwargs))

    def test_purchase_basis_range_selects_by_purchase_date(self):
        rows = self.rows(
            date_from=datetime.date(2026, 4, 1), date_to=datetime.date(2026, 4, 30)
        )
        self.assertEqual([r.pk for r in rows], [self.april.pk])

    def test_undated_rows_drop_out_of_a_purchase_range(self):
        rows = self.rows(
            date_from=datetime.date(2026, 1, 1), date_to=datetime.date(2026, 12, 31)
        )
        self.assertNotIn(self.undated.pk, [r.pk for r in rows])

    def test_undated_rows_are_included_without_a_range(self):
        self.assertIn(self.undated.pk, [r.pk for r in self.rows()])

    def test_installed_basis_uses_the_creation_date(self):
        # Everything was fitted today, so today's range must return all three
        # even though one has no purchase date and another was bought in March.
        today = datetime.date.today()
        rows = self.rows(basis="installed", date_from=today, date_to=today)
        self.assertEqual(len(rows), 3)

    def test_vendor_filter(self):
        rows = self.rows(vendor_ids=[self.vendor_b.pk])
        self.assertEqual([r.pk for r in rows], [self.april.pk])

    def test_component_type_filter(self):
        rows = self.rows(ctype_ids=[self.storage.pk])
        self.assertEqual([r.pk for r in rows], [self.april.pk])

    def test_status_filter_separates_installed_from_removed(self):
        remove_component(self.asset, self.march, self.user, note="failed")
        self.assertNotIn(self.march.pk, [r.pk for r in self.rows(status="installed")])
        self.assertEqual([r.pk for r in self.rows(status="removed")], [self.march.pk])

    def test_summary_totals_only_the_costed_rows(self):
        summary = report.summarise(self.rows())
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["total_cost"], Decimal("17000.00"))
        self.assertEqual(summary["costed"], 2)
        self.assertEqual(summary["uncosted"], 1)

    def test_summary_groups_by_vendor_ordered_by_spend(self):
        summary = report.summarise(self.rows())
        self.assertEqual(
            [(v["name"], v["count"], v["cost"]) for v in summary["vendors"]],
            [
                ("Star Tech", 1, Decimal("10000.00")),
                ("Ryans Computers", 1, Decimal("7000.00")),
                ("— No vendor —", 1, Decimal("0")),
            ],
        )

    def test_summary_groups_by_month_oldest_first_with_undated_last(self):
        summary = report.summarise(self.rows())
        self.assertEqual([p["name"] for p in summary["periods"]][-1], "No date")
        dated = [p["name"] for p in summary["periods"] if p["name"] != "No date"]
        self.assertEqual(dated[:2], ["Mar 2026", "Apr 2026"])

    def test_summary_can_group_by_day(self):
        summary = report.summarise(self.rows(), group="day")
        self.assertIn("12 Mar 2026", [p["name"] for p in summary["periods"]])

    def test_summary_groups_by_component(self):
        summary = report.summarise(self.rows())
        self.assertEqual(
            {p["name"] for p in summary["parts"]}, {"RAM", "Storage", "Keyboard"}
        )


# ── HTTP ──────────────────────────────────────────────────────────────────────

class ComponentReportViewTests(ComponentFixture):
    def setUp(self):
        super().setUp()
        self.component = self.fit(serial="SN-1")
        self.client.force_login(self.user)

    def test_view_page_renders_with_the_summary(self):
        resp = self.client.get(reverse("reports:components_view"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["summary"]["total"], 1)
        self.assertContains(resp, "PC-0001")

    def test_summary_covers_the_whole_report_not_just_the_page(self):
        for i in range(3):
            self.fit(serial=f"SN-EXTRA-{i}")
        resp = self.client.get(reverse("reports:components_view"), {"per_page": 25})
        # 4 rows total; one page of 25 holds them all, so force a narrow page.
        resp = self.client.get(reverse("reports:components_view") + "?per_page=25&page=1")
        self.assertEqual(resp.context["summary"]["total"], 4)
        self.assertEqual(resp.context["total_count"], 4)

    def test_view_page_honours_the_vendor_filter(self):
        resp = self.client.get(
            reverse("reports:components_view"), {"vendor": str(self.vendor_b.pk)}
        )
        self.assertEqual(resp.context["summary"]["total"], 0)

    def test_excel_download(self):
        resp = self.client.get(reverse("reports:components_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(XLSX_MAGIC))

    def test_pdf_download(self):
        resp = self.client.get(reverse("reports:components_pdf"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_column_picker_narrows_the_table(self):
        resp = self.client.get(
            reverse("reports:components_view"), {"cols": "asset_tag,cost"}
        )
        self.assertEqual(
            [k for k, _ in resp.context["selected_cols"]], ["asset_tag", "cost"]
        )


class ComponentPanelTests(ComponentFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse("lifecycle:component_panel", args=[self.asset.pk])

    def test_panel_offers_exactly_the_parts_mapped_to_this_sub_asset(self):
        resp = self.client.get(self.url)
        offered = {c.code for c in resp.context["component_types"]}
        # Only what is mapped to the PC Set: the SFP belongs to the router, and
        # the unmapped part belongs nowhere. Nothing else may leak in.
        self.assertEqual(offered, {"ram", "storage-drive", "keyboard"})

    def test_panel_refuses_an_unmapped_part(self):
        resp = self.client.post(self.url, {
            "action": "add", "ctype": str(self.unmapped.pk),
        })
        self.assertIn("not offered", resp.context["error"])
        self.assertEqual(self.asset.components.count(), 0)

    def test_deactivating_a_part_withdraws_it_from_the_panel(self):
        self.ram.is_active = False
        self.ram.save(update_fields=["is_active"])
        resp = self.client.get(self.url)
        self.assertNotIn("ram", {c.code for c in resp.context["component_types"]})

    def test_panel_does_not_leak_template_source(self):
        # A multi-line {# #} comment is not a comment in Django — it renders as
        # literal text, and markup inside it becomes real elements. That is what
        # broke this drawer once; the field partial now uses {% comment %}.
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("{#", html)
        self.assertNotIn("{%", html)

    def test_add_records_the_purchase_details(self):
        resp = self.client.post(self.url, {
            "action": "add",
            "ctype": str(self.ram.pk),
            "capacity": "32",
            "unit": "GB",
            "brand": "Corsair",
            "model_name": "Vengeance",
            "serial_number": "SN-77",
            "cost": "18000",
            "vendor": str(self.vendor_b.pk),
            "purchase_date": "2026-03-01",
            "purchase_order": "WO-12",
        })
        self.assertEqual(resp.status_code, 200)
        component = self.asset.components.get(serial_number="SN-77")
        self.assertEqual(component.capacity_display, "32 GB")
        self.assertEqual(component.cost, Decimal("18000"))
        self.assertEqual(component.vendor, self.vendor_b)
        self.assertEqual(component.purchase_date, datetime.date(2026, 3, 1))
        self.assertEqual(component.purchase_order, "WO-12")

    def test_single_unit_part_needs_no_posted_unit(self):
        self.client.post(self.url, {
            "action": "add", "ctype": str(self.ram.pk), "capacity": "8",
        })
        self.assertEqual(self.asset.components.get(capacity=8).unit, "GB")

    def test_a_part_from_another_sub_asset_is_refused(self):
        resp = self.client.post(self.url, {
            "action": "add", "ctype": str(self.sfp.pk),
        })
        self.assertIn("not offered", resp.context["error"])
        self.assertEqual(self.asset.components.count(), 0)

    def test_future_purchase_date_is_refused(self):
        future = datetime.date.today() + datetime.timedelta(days=1)
        resp = self.client.post(self.url, {
            "action": "add", "ctype": str(self.ram.pk), "capacity": "8",
            "purchase_date": future.isoformat(),
        })
        self.assertIn("future", resp.context["error"])
        self.assertEqual(self.asset.components.count(), 0)

    def test_non_numeric_cost_is_refused(self):
        resp = self.client.post(self.url, {
            "action": "add", "ctype": str(self.ram.pk), "capacity": "8",
            "cost": "twelve",
        })
        self.assertIn("Cost", resp.context["error"])
        self.assertEqual(self.asset.components.count(), 0)

    def test_missing_capacity_reports_the_model_rule(self):
        resp = self.client.post(self.url, {
            "action": "add", "ctype": str(self.ram.pk),
        })
        self.assertIn("capacity", resp.context["error"].lower())


# ── Template hygiene ──────────────────────────────────────────────────────────

class TemplateCommentTests(TestCase):
    """
    Django's ``{# #}`` comment cannot span lines — the parser only recognises it
    within a single line, so a multi-line one is emitted as literal page text and
    any markup inside it becomes real elements. It fails silently: no exception,
    no check error, just a broken page. This lives here because that bug is what
    broke the component drawer; the guard is project-wide.
    """

    def test_no_multiline_comment_tags_in_templates(self):
        import re
        from pathlib import Path

        from django.conf import settings

        offenders = []
        roots = [Path(settings.BASE_DIR) / "templates"]
        roots += [Path(settings.BASE_DIR) / app / "templates"
                  for app in ("assets", "assignees", "assignments", "catalogue",
                              "lifecycle", "locations", "qrcodes", "reports", "sync_prp")]

        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.html"):
                text = path.read_text(encoding="utf-8")
                for match in re.finditer(r"\{#.*?#\}", text, re.S):
                    if "\n" in match.group(0):
                        line = text[: match.start()].count("\n") + 1
                        offenders.append(f"{path.relative_to(settings.BASE_DIR)}:{line}")

        self.assertEqual(
            offenders, [],
            "Multi-line {# #} comments render as visible text — use "
            "{% comment %}…{% endcomment %} instead:\n  " + "\n  ".join(offenders),
        )
