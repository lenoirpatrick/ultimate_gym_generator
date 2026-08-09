from django.contrib import admin

from .models import Workout, WorkoutExercise


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0
    raw_id_fields = ("exercise",)


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("user", "format", "duration_minutes", "created_at")
    list_filter = ("format", "duration_minutes")
    inlines = (WorkoutExerciseInline,)
