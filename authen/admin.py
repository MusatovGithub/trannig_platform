from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from authen.models import Company, CustomUser, Gender, TypeSportsCompany

admin.site.register(Gender)


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = [
        "username",
        "first_name",
        "last_name",
    ]
    search_fields = [
        "username",
        "first_name",
        "last_name",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "username",
                    "email",
                    "password",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "groups",
                    "user_permissions",
                    "company",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        (
            "Personal Information",
            {
                "fields": (
                    "phone",
                    "avatar",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


admin.site.register(CustomUser, CustomUserAdmin)

admin.site.register(Company)

admin.site.register(TypeSportsCompany)
