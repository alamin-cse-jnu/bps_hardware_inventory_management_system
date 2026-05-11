import io

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path

from .models import AssetCategory, AssetComponent, AssetItem, AssetType
from .services.excel_import import (
    SESSION_KEY_COLS,
    SESSION_KEY_ROWS,
    SESSION_KEY_TYPE,
    FIXED_COLUMNS,
    ExcelImportExecutor,
    ExcelImportValidator,
    ExcelTemplateGenerator,
)


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "name_bn", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "name_bn")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "name_bn", "category", "has_components", "is_active")
    list_filter = ("category", "has_components", "is_active")
    search_fields = ("name", "name_bn")
    readonly_fields = ("created_at", "updated_at")


class AssetComponentInline(admin.TabularInline):
    model = AssetComponent
    fields = (
        "component_type",
        "brand",
        "model_name",
        "serial_number",
        "is_active",
        "removed_at",
        "removal_reason",
    )
    extra = 0
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("parent_asset__asset_type")


@admin.register(AssetItem)
class AssetItemAdmin(admin.ModelAdmin):
    change_list_template = "admin/assets/assetitem/change_list.html"

    list_display = (
        "asset_tag",
        "asset_type",
        "brand",
        "model_name",
        "status",
        "storage_location",
        "is_deleted",
    )
    list_filter = ("status", "asset_type__category", "is_deleted")
    search_fields = ("asset_tag", "serial_number", "brand", "model_name")
    readonly_fields = ("created_at", "updated_at", "deleted_at", "is_assignable")

    fieldsets = (
        ("Identity", {
            "fields": ("asset_tag", "asset_type", "brand", "model_name", "serial_number"),
        }),
        ("Status & Location", {
            "fields": ("status", "storage_location", "is_assignable"),
        }),
        ("Specifications", {
            "fields": ("specifications",),
        }),
        ("Procurement", {
            "fields": (
                "purchase_date",
                "purchase_order",
                "supplier",
                "purchase_cost",
                "warranty_expiry",
                "amc_expiry",
            ),
            "classes": ("collapse",),
        }),
        ("Notes", {
            "fields": ("notes",),
        }),
        ("Audit", {
            "fields": ("created_by", "created_at", "updated_at", "is_deleted", "deleted_at"),
            "classes": ("collapse",),
        }),
    )

    # ------------------------------------------------------------------
    # Inline
    # ------------------------------------------------------------------

    def get_inline_instances(self, request, obj=None):
        if obj and obj.asset_type.has_components:
            return [AssetComponentInline(self.model, self.admin_site)]
        return []

    # ------------------------------------------------------------------
    # Readonly / save
    # ------------------------------------------------------------------

    def get_readonly_fields(self, request, obj=None):
        base = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_deleted:
            all_fields = [f.name for f in obj._meta.get_fields() if hasattr(f, "name")]
            return list(set(base + all_fields))
        return base

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # ------------------------------------------------------------------
    # Custom URLs
    # ------------------------------------------------------------------

    def get_urls(self):
        custom = [
            path(
                "download-template/",
                self.admin_site.admin_view(self.download_template_view),
                name="assets_assetitem_download_template",
            ),
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="assets_assetitem_import",
            ),
            path(
                "import/confirm/",
                self.admin_site.admin_view(self.import_confirm_view),
                name="assets_assetitem_import_confirm",
            ),
        ]
        return custom + super().get_urls()

    # ------------------------------------------------------------------
    # Download template view
    # ------------------------------------------------------------------

    def download_template_view(self, request):
        type_id = request.GET.get("type_id")
        if not type_id:
            messages.error(request, "No asset type selected.")
            return redirect("admin:assets_assetitem_import")
        try:
            asset_type = AssetType.objects.get(pk=type_id, is_active=True)
        except AssetType.DoesNotExist:
            messages.error(request, "Asset type not found.")
            return redirect("admin:assets_assetitem_import")

        wb = ExcelTemplateGenerator().generate_template(asset_type.pk)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"import_template_{asset_type.name.lower().replace(' ', '_')}.xlsx"
        response = HttpResponse(
            buf.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    # ------------------------------------------------------------------
    # Import view (upload form + validation preview)
    # ------------------------------------------------------------------

    def import_view(self, request):
        asset_types = AssetType.objects.filter(is_active=True).select_related("category")
        context = {
            **self.admin_site.each_context(request),
            "title": "Import Assets from Excel",
            "asset_types": asset_types,
            "opts": self.model._meta,
        }

        if request.method == "GET":
            # Clear any stale session data
            request.session.pop(SESSION_KEY_ROWS, None)
            request.session.pop(SESSION_KEY_TYPE, None)
            return render(request, "admin/assets/assetitem/import_form.html", context)

        # POST — validate uploaded file
        type_id = request.POST.get("asset_type_id")
        uploaded_file = request.FILES.get("excel_file")

        if not type_id:
            messages.error(request, "Please select an asset type.")
            return render(request, "admin/assets/assetitem/import_form.html", context)

        if not uploaded_file:
            messages.error(request, "Please select an Excel file to upload.")
            return render(request, "admin/assets/assetitem/import_form.html", context)

        try:
            validated_rows = ExcelImportValidator().validate(uploaded_file, int(type_id))
        except Exception as exc:
            messages.error(request, f"Could not read file: {exc}")
            return render(request, "admin/assets/assetitem/import_form.html", context)

        # Persist validated data in session for the confirm step
        request.session[SESSION_KEY_ROWS] = validated_rows
        request.session[SESSION_KEY_TYPE] = int(type_id)

        # Build column list for the preview table
        asset_type = AssetType.objects.get(pk=type_id)
        spec_cols = [f"spec_{k}" for k in (asset_type.spec_schema or [])]
        all_cols = FIXED_COLUMNS + spec_cols
        request.session[SESSION_KEY_COLS] = all_cols

        counts = {
            "valid": sum(1 for r in validated_rows if r["status"] == "valid"),
            "warning": sum(1 for r in validated_rows if r["status"] == "warning"),
            "error": sum(1 for r in validated_rows if r["status"] == "error"),
            "total": len(validated_rows),
        }

        return render(
            request,
            "admin/assets/assetitem/import_preview.html",
            {
                **context,
                "title": "Import Preview",
                "validated_rows": validated_rows,
                "counts": counts,
                "all_columns": all_cols,
                "asset_type": asset_type,
            },
        )

    # ------------------------------------------------------------------
    # Confirm view (execute)
    # ------------------------------------------------------------------

    def import_confirm_view(self, request):
        if request.method != "POST":
            return redirect("admin:assets_assetitem_import")

        validated_rows = request.session.get(SESSION_KEY_ROWS)
        type_id = request.session.get(SESSION_KEY_TYPE)

        if not validated_rows or not type_id:
            messages.error(request, "Import session expired. Please upload the file again.")
            return redirect("admin:assets_assetitem_import")

        # Filter to only the rows the user confirmed (by row index)
        selected_indices = set(request.POST.getlist("selected_rows"))
        if selected_indices:
            rows_to_import = [
                r for r in validated_rows
                if str(r["row"]) in selected_indices and r["status"] in ("valid", "warning")
            ]
        else:
            rows_to_import = [
                r for r in validated_rows if r["status"] in ("valid", "warning")
            ]

        result = ExcelImportExecutor().execute(rows_to_import, type_id, request.user)

        # Clear session
        request.session.pop(SESSION_KEY_ROWS, None)
        request.session.pop(SESSION_KEY_TYPE, None)
        request.session.pop(SESSION_KEY_COLS, None)

        if result["errors"]:
            messages.error(
                request,
                f"Import failed and was rolled back. Errors: {'; '.join(result['errors'][:3])}",
            )
        else:
            messages.success(
                request,
                f"Import complete: {result['created']} asset(s) created, "
                f"{result['skipped']} row(s) skipped.",
            )

        return redirect("admin:assets_assetitem_changelist")


@admin.register(AssetComponent)
class AssetComponentAdmin(admin.ModelAdmin):
    list_display = (
        "parent_asset",
        "component_type",
        "brand",
        "model_name",
        "serial_number",
        "is_active",
        "removed_at",
    )
    list_filter = ("component_type", "is_active")
    search_fields = (
        "parent_asset__asset_tag",
        "serial_number",
        "brand",
        "model_name",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("parent_asset",)
