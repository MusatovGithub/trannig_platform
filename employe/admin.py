from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from import_export.admin import ImportExportModelAdmin

from employe.models import (
    Employe,
    EmployePermissions,
    EmployePermissionsGroups,
    EmployeRoll,
)


class AdminEmployeRoll(admin.ModelAdmin):
    list_display = ["id", "name"]


admin.site.register(EmployeRoll, AdminEmployeRoll)


class AdminEpmloye(admin.ModelAdmin):
    list_display = ["id", "full_name", "phone"]


admin.site.register(Employe, AdminEpmloye)


@admin.register(EmployePermissions)
class EmployePermissionsAdmin(ImportExportModelAdmin):
    pass


# admin.site.register(EmployePermissions)


class LimitEmployePermissions(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # count all forms that have not been marked for deletion
        count = sum(
            1 for form in self.forms if not self._should_delete_form(form)
        )
        max_num = 10  # specify your max number of images here
        if count > max_num:
            raise ValidationError(
                f"You can only associate up to {max_num} images with this product."
            )


class EmployePermissionsInline(admin.TabularInline):
    model = EmployePermissions
    formset = LimitEmployePermissions
    extra = 1
    min_num = 1
    max_num = 50


class AdminEmployePermissionsGroups(ImportExportModelAdmin):
    inlines = [
        EmployePermissionsInline,
    ]
    list_display = ["id", "name"]
    search_fields = ["id", "name"]


admin.site.register(EmployePermissionsGroups, AdminEmployePermissionsGroups)
