from django.contrib import admin

from . import models


@admin.register(models.Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "logo")
    search_fields = ("name",)


@admin.register(models.Retailer)
class RetailerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "brand", "state", "municipality", "lat", "lng")
    list_filter = ("state", "brand")
    search_fields = ("name", "address", "state", "municipality")
    autocomplete_fields = ("brand",)
