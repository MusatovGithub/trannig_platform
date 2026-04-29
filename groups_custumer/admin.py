from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from groups_custumer.models import (
    ClasessProgramm,
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
    Schedule,
    TypeSports,
    Week,
)


@admin.register(GroupClasses)
class GroupClassesAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "groups_id", "date", "strat", "end"]
    search_fields = ["name", "groups_id__name", "date"]
    list_filter = ["date", "groups_id"]


class GroupClassessCustumerAdmin(admin.ModelAdmin):
    list_display = ["id", "gr_class", "custumer", "date", "attendance_status"]
    search_fields = [
        "id",
        "gr_class__name",
        "custumer__full_name",
        "date",
        "attendance_status",
    ]
    autocomplete_fields = ["custumer", "gr_class"]
    list_filter = ["attendance_status"]


admin.site.register(GroupClassessCustumer, GroupClassessCustumerAdmin)


class ClasessProgrammAdmin(admin.ModelAdmin):
    list_display = ["id", "classes", "stages", "distance", "style", "rest"]
    search_fields = ["classes__name", "stages", "distance", "style", "rest"]
    list_filter = ["stages", "distance", "style", "rest"]
    autocomplete_fields = ["classes"]


admin.site.register(ClasessProgramm, ClasessProgrammAdmin)
admin.site.register(TypeSports)
admin.site.register(Week)


class LimitGroupClasses(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # count all forms that have not been marked for deletion
        count = sum(
            1 for form in self.forms if not self._should_delete_form(form)
        )
        max_num = 100000000  # specify your max number of images here
        if count > max_num:
            raise ValidationError(
                f"You can only associate up to {max_num} images with this product."  # noqa: E501
            )


class GroupClassesInline(admin.TabularInline):
    model = GroupClasses
    formset = LimitGroupClasses
    extra = 1
    min_num = 1
    max_num = 100000000


class LimitSchedule(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # count all forms that have not been marked for deletion
        count = sum(
            1 for form in self.forms if not self._should_delete_form(form)
        )
        max_num = 7  # specify your max number of images here
        if count > max_num:
            raise ValidationError(
                f"You can only associate up to {max_num} images with this product."  # noqa: E501
            )


class ScheduleInline(admin.TabularInline):
    model = Schedule
    formset = LimitSchedule
    extra = 1
    min_num = 1
    max_num = 7


class AdminGroupsClass(admin.ModelAdmin):
    inlines = [ScheduleInline, GroupClassesInline]
    list_display = ["id", "name", "type_sport", "strat_training"]
    search_fields = ["name", "type_sport", "strat_training"]
    list_filter = ["name"]


admin.site.register(GroupsClass, AdminGroupsClass)
