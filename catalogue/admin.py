from django.contrib import admin

from .models import CatalogBrand, CatalogModel, SubAssetSpecField


@admin.register(CatalogBrand)
class CatalogBrandAdmin(admin.ModelAdmin):
    list_display = ("name", "sub_asset", "is_active")
    list_filter = ("is_active", "sub_asset__category")
    search_fields = ("name",)


@admin.register(CatalogModel)
class CatalogModelAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "brand__name")


@admin.register(SubAssetSpecField)
class SubAssetSpecFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "sub_asset", "widget", "order", "is_active")
    list_filter = ("widget", "is_active", "sub_asset__category")
    search_fields = ("label", "key")
    ordering = ("sub_asset", "order")
