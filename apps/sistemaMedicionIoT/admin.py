from django.contrib import admin

from .models import Measurement


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):

    list_display = (
        "station",
        "process",
        "time_ms",
        "created_at",
    )

    search_fields = (
        "station",
        "process",
    )

    list_filter = (
        "station",
        "process",
    )

    ordering = (
        "-created_at",
    )