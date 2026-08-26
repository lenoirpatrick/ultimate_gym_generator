from django.contrib import admin

from .models import Activity, ApiKey, DailySteps, WeightMeasurement


@admin.register(WeightMeasurement)
class WeightMeasurementAdmin(admin.ModelAdmin):
    list_display = ("user", "weight_kg", "recorded_at", "source")
    list_filter = ("source",)
    date_hierarchy = "recorded_at"
    search_fields = ("user__email", "source")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "activity_type", "started_at", "distance_meters", "source")
    list_filter = ("activity_type", "source")
    date_hierarchy = "started_at"
    search_fields = ("user__email", "source")


@admin.register(DailySteps)
class DailyStepsAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "steps")
    date_hierarchy = "date"
    search_fields = ("user__email",)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "prefix", "created_at", "last_used_at")
    search_fields = ("user__email", "label", "prefix")
    readonly_fields = ("prefix", "hashed_key", "created_at", "last_used_at")
