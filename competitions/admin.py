from django.contrib import admin

from competitions.models import Competitions, CustumerCompetitionResult


@admin.register(Competitions)
class CompetitionsAdmin(admin.ModelAdmin):
    """Админка для соревнований."""

    list_display = ["name", "location", "date", "end_date", "status", "owner"]
    list_filter = ["status", "date", "end_date"]
    search_fields = ["name", "location"]


@admin.register(CustumerCompetitionResult)
class CustumerCompetitionResultAdmin(admin.ModelAdmin):
    """Админка для результатов соревнований."""

    list_display = [
        "customer",
        "competition",
        "distance",
        "formatted_time_display",
        "place",
        "is_disqualified",
    ]
    list_filter = ["competition", "is_disqualified"]
    search_fields = ["customer__first_name", "customer__last_name"]

    def formatted_time_display(self, obj):
        """Отображение времени в формате мм:сс:ммм."""
        if obj.is_disqualified:
            return "Дисквалифицирован"
        return obj.format_time() or "—"

    formatted_time_display.short_description = "Время"
