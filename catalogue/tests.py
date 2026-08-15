import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from assets.models import AssetCategory, AssetType
from catalogue import specs as catalogue_specs
from catalogue.models import CatalogBrand, CatalogModel, SubAssetSpecField

User = get_user_model()


class CatalogueSetupMixin:
    def build_tree(self):
        self.main = AssetCategory.objects.create(name="Computing Equipment")
        self.main_off = AssetCategory.objects.create(name="Retired Main", is_active=False)
        self.sub = AssetType.objects.create(category=self.main, name="Laptop")
        self.sub_off = AssetType.objects.create(category=self.main, name="Old Laptop", is_active=False)
        self.brand = CatalogBrand.objects.create(sub_asset=self.sub, name="HP")
        self.brand_off = CatalogBrand.objects.create(sub_asset=self.sub, name="Defunct", is_active=False)
        self.model = CatalogModel.objects.create(brand=self.brand, name="ProBook 440 G10")
        self.model_off = CatalogModel.objects.create(brand=self.brand, name="Old Model", is_active=False)
        # Spec fields for the Sub Asset
        SubAssetSpecField.objects.create(sub_asset=self.sub, key="ram", label="RAM", widget="units", options=["GB", "TB"], order=0)
        SubAssetSpecField.objects.create(sub_asset=self.sub, key="licensed", label="Licensed", widget="toggle", options=["Yes", "No"], order=1)
        SubAssetSpecField.objects.create(sub_asset=self.sub, key="display", label="Display", widget="number", unit="inches", order=2)
        SubAssetSpecField.objects.create(sub_asset=self.sub, key="hidden", label="Hidden", widget="text", is_active=False, order=3)


class CascadeApiTests(CatalogueSetupMixin, TestCase):
    def setUp(self):
        self.build_tree()
        self.user = User.objects.create_superuser("admin", "a@x.com", "pw")
        self.client.force_login(self.user)

    def _ids(self, resp):
        return {r["id"] for r in json.loads(resp.content)["results"]}

    def test_sub_assets_filtered_by_main_and_active(self):
        resp = self.client.get(reverse("catalogue:api_sub_assets"), {"main": self.main.pk})
        self.assertEqual(self._ids(resp), {self.sub.pk})  # inactive sub excluded

    def test_brands_filtered_by_sub_and_active(self):
        resp = self.client.get(reverse("catalogue:api_brands"), {"sub": self.sub.pk})
        self.assertEqual(self._ids(resp), {self.brand.pk})  # inactive brand excluded

    def test_models_filtered_by_brand_and_active(self):
        resp = self.client.get(reverse("catalogue:api_models"), {"brand": self.brand.pk})
        self.assertEqual(self._ids(resp), {self.model.pk})  # inactive model excluded

    def test_spec_endpoint_returns_active_fields_for_models_sub_asset(self):
        resp = self.client.get(reverse("catalogue:api_spec"), {"model": self.model.pk})
        data = json.loads(resp.content)
        self.assertEqual(data["sub_asset"], self.sub.pk)
        keys = [f["key"] for f in data["fields"]]
        self.assertEqual(keys, ["ram", "licensed", "display"])  # ordered, "hidden" excluded
        self.assertIn("specification_template", data)

    def test_empty_params_return_empty(self):
        for name in ("api_sub_assets", "api_brands", "api_models"):
            resp = self.client.get(reverse(f"catalogue:{name}"))
            self.assertEqual(json.loads(resp.content)["results"], [])


class SpecHelperTests(CatalogueSetupMixin, TestCase):
    def setUp(self):
        self.build_tree()

    def test_collect_values_handles_units_and_scalars(self):
        post = {
            "spec_ram": "16", "spec_ram_unit": "GB",
            "spec_licensed": "Yes",
            "spec_display": "14",
            "spec_hidden": "ignored",  # inactive field — must be skipped
        }
        specs = catalogue_specs.collect_values(self.sub, post)
        self.assertEqual(specs, {
            "ram": {"qty": "16", "unit": "GB"},
            "licensed": "Yes",
            "display": "14",
        })

    def test_display_rows_formats_units_and_number(self):
        specs = {"ram": {"qty": "16", "unit": "GB"}, "licensed": "Yes", "display": "14"}
        rows = dict(catalogue_specs.display_rows(self.sub, specs))
        self.assertEqual(rows["RAM"], "16 GB")
        self.assertEqual(rows["Display"], "14 inches")
        self.assertEqual(rows["Licensed"], "Yes")

    def test_form_values_roundtrips_existing_values(self):
        specs = {"ram": {"qty": "8", "unit": "TB"}, "licensed": "No"}
        rows = {r["key"]: r for r in catalogue_specs.form_values(self.sub, specs)}
        self.assertEqual(rows["ram"]["qty"], "8")
        self.assertEqual(rows["ram"]["unit"], "TB")
        self.assertEqual(rows["licensed"]["value"], "No")

    def test_form_values_keeps_number_widget_unit_badge(self):
        # Regression: the fixed unit must survive into the form so the badge renders.
        rows = {r["key"]: r for r in catalogue_specs.form_values(self.sub, {})}
        self.assertEqual(rows["display"]["unit"], "inches")

    def test_units_widget_falls_back_to_unit_when_no_options(self):
        # Admin entered the chip value in the Unit field instead of Options.
        f = SubAssetSpecField.objects.create(
            sub_asset=self.sub, key="cpu_core", label="CPU Core",
            widget="units", unit="cores", options=[], order=9,
        )
        rows = {r["key"]: r for r in catalogue_specs.form_values(self.sub, {})}
        self.assertEqual(rows["cpu_core"]["options"], ["cores"])
        f.delete()


class ManagePageTests(CatalogueSetupMixin, TestCase):
    def setUp(self):
        self.build_tree()
        self.admin = User.objects.create_superuser("admin", "a@x.com", "pw")
        self.client.force_login(self.admin)

    def test_manage_page_renders_selected_tree(self):
        resp = self.client.get(reverse("catalogue:manage"), {
            "main": self.main.pk, "sub": self.sub.pk, "brand": self.brand.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ProBook 440 G10")
        self.assertContains(resp, "Specification fields")

    def test_brand_create_under_sub(self):
        resp = self.client.post(reverse("catalogue:brand_save"), {
            "main": self.main.pk, "sub": self.sub.pk, "name": "Dell",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(CatalogBrand.objects.filter(sub_asset=self.sub, name="Dell").exists())

    def test_specfield_create_slugifies_key(self):
        self.client.post(reverse("catalogue:specfield_save"), {
            "main": self.main.pk, "sub": self.sub.pk,
            "label": "Storage Type", "widget": "select", "options": "SSD, HDD",
        })
        field = SubAssetSpecField.objects.get(sub_asset=self.sub, key="storage_type")
        self.assertEqual(field.options, ["SSD", "HDD"])

    def test_manage_page_shows_in_use_badge_and_disables_delete(self):
        from assets.models import AssetItem
        AssetItem.objects.create(
            asset_tag="PT-9001", asset_type=self.sub, brand="HP", model_name="ProBook 440 G10",
        )
        resp = self.client.get(reverse("catalogue:manage"), {
            "main": self.main.pk, "sub": self.sub.pk, "brand": self.brand.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "in use")        # usage badge rendered
        self.assertContains(resp, "btn-del-off")   # delete disabled for in-use node

    # ── Delete rule: allowed when no asset uses the node; cascades children ──

    def _make_asset(self, *, brand="HP", model_name="ProBook 440 G10", asset_type=None):
        from assets.models import AssetItem
        return AssetItem.objects.create(
            asset_tag=f"PT-{AssetItem.objects.count() + 1:04d}",
            asset_type=asset_type or self.sub,
            brand=brand,
            model_name=model_name,
        )

    def test_brand_delete_cascades_models_when_no_assets(self):
        resp = self.client.post(reverse("catalogue:brand_delete", args=[self.brand.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CatalogBrand.objects.filter(pk=self.brand.pk).exists())
        self.assertFalse(CatalogModel.objects.filter(pk=self.model.pk).exists())  # cascaded

    def test_brand_delete_blocked_when_asset_uses_brand_name(self):
        self._make_asset(brand="HP")
        resp = self.client.post(reverse("catalogue:brand_delete", args=[self.brand.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(CatalogBrand.objects.filter(pk=self.brand.pk).exists())

    def test_model_delete_blocked_when_asset_uses_model_name(self):
        self._make_asset(brand="HP", model_name="ProBook 440 G10")
        resp = self.client.post(reverse("catalogue:model_delete", args=[self.model.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(CatalogModel.objects.filter(pk=self.model.pk).exists())

    def test_model_delete_allowed_when_no_asset_uses_it(self):
        resp = self.client.post(reverse("catalogue:model_delete", args=[self.model.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CatalogModel.objects.filter(pk=self.model.pk).exists())

    def test_sub_delete_cascades_brands_models_specs_when_no_assets(self):
        resp = self.client.post(reverse("catalogue:sub_delete", args=[self.sub.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AssetType.objects.filter(pk=self.sub.pk).exists())
        self.assertFalse(CatalogBrand.objects.filter(sub_asset_id=self.sub.pk).exists())
        self.assertFalse(SubAssetSpecField.objects.filter(sub_asset_id=self.sub.pk).exists())

    def test_sub_delete_blocked_when_asset_of_type_exists(self):
        self._make_asset(asset_type=self.sub)
        resp = self.client.post(reverse("catalogue:sub_delete", args=[self.sub.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AssetType.objects.filter(pk=self.sub.pk).exists())

    def test_main_delete_cascades_whole_subtree_when_no_assets(self):
        resp = self.client.post(reverse("catalogue:main_delete", args=[self.main.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AssetCategory.objects.filter(pk=self.main.pk).exists())
        self.assertFalse(AssetType.objects.filter(category_id=self.main.pk).exists())

    def test_main_delete_blocked_when_asset_uses_a_sub(self):
        self._make_asset(asset_type=self.sub)
        resp = self.client.post(reverse("catalogue:main_delete", args=[self.main.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AssetCategory.objects.filter(pk=self.main.pk).exists())

    def test_deleted_asset_does_not_block_delete(self):
        a = self._make_asset(brand="HP")
        a.is_deleted = True
        a.save(update_fields=["is_deleted"])
        resp = self.client.post(reverse("catalogue:brand_delete", args=[self.brand.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CatalogBrand.objects.filter(pk=self.brand.pk).exists())


class AssetFormIntegrationTests(CatalogueSetupMixin, TestCase):
    """The Add/Edit Asset form is rewired to the cascade — smoke-test it renders & saves."""

    def setUp(self):
        self.build_tree()
        self.admin = User.objects.create_superuser("admin", "a@x.com", "pw")
        self.client.force_login(self.admin)

    def test_create_form_renders_cascade(self):
        resp = self.client.get(reverse("assets:create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="cat-main"')
        self.assertContains(resp, "Main Asset")

    def test_spec_fields_htmx_renders_widgets(self):
        resp = self.client.get(reverse("assets:spec_fields"), {"asset_type": self.sub.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "RAM")
        self.assertContains(resp, "spec_ram_unit")  # units widget chips

    def test_create_asset_collects_master_data_specs(self):
        from assets.models import AssetItem
        resp = self.client.post(reverse("assets:create"), {
            "asset_type": self.sub.pk,
            "brand": "HP",
            "model_name": "ProBook 440 G10",
            "spec_ram": "16", "spec_ram_unit": "GB",
            "spec_licensed": "Yes",
            "spec_display": "14",
        })
        self.assertEqual(resp.status_code, 302)
        asset = AssetItem.objects.get(brand="HP", model_name="ProBook 440 G10")
        self.assertEqual(asset.asset_type, self.sub)
        self.assertEqual(asset.specifications["ram"], {"qty": "16", "unit": "GB"})
        self.assertEqual(asset.specifications["licensed"], "Yes")
        self.assertEqual(asset.specifications["display"], "14")
