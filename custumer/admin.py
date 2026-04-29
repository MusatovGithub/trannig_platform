from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from custumer.models import (
    Cashier,
    Custumer,
    CustumerDocs,
    CustumerRepresentatives,
    CustumerSubscription,
    CustumerSubscriptonPayment,
    PointsHistory,
    SportCategory,
    SubscriptionTemplate,
    TypeRepresentatives,
)

admin.site.site_header = "Админ Цунамис"
admin.site.site_title = "Админ Цунамис"
admin.site.index_title = "Панель управления"


@admin.register(SportCategory)
class SportCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "level", "description"]
    list_editable = ["level"]
    ordering = ["level"]
    search_fields = ["name"]
    list_filter = ["level"]

    fieldsets = (
        ("Основная информация", {"fields": ("name", "level")}),
        (
            "Дополнительно",
            {"fields": ("description",), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("level")


admin.site.register(TypeRepresentatives)
admin.site.register(Cashier)
admin.site.register(PointsHistory)
admin.site.register(SubscriptionTemplate)


@admin.register(CustumerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "custumer",
        "count_of_trainnig_left",
    ]
    search_fields = [
        "id",
        "custumer__full_name",
    ]
    list_filter = [
        "is_blok",
        "is_free",
    ]


class LimitCustumerSubscription(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # count all forms that have not been marked for deletion
        count = sum(
            1 for form in self.forms if not self._should_delete_form(form)
        )
        max_num = 10  # specify your max number of images here
        if count > max_num:
            raise ValidationError(
                f"You can only associate up to {max_num} images with this product."  # noqa: E501
            )


class CustumerSubscriptionInline(admin.TabularInline):
    model = CustumerSubscription
    formset = LimitCustumerSubscription
    extra = 1
    min_num = 1
    max_num = 10


class LimitCustumerDocs(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # count all forms that have not been marked for deletion
        count = sum(
            1 for form in self.forms if not self._should_delete_form(form)
        )
        max_num = 10  # specify your max number of images here
        if count > max_num:
            raise ValidationError(
                f"You can only associate up to {max_num} images with this product."  # noqa: E501
            )


class CustumerDocsInline(admin.TabularInline):
    model = CustumerDocs
    formset = LimitCustumerDocs
    extra = 1
    min_num = 1
    max_num = 10


class LimitCustumerRepresentatives(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # count all forms that have not been marked for deletion
        count = sum(
            1 for form in self.forms if not self._should_delete_form(form)
        )
        max_num = 10  # specify your max number of images here
        if count > max_num:
            raise ValidationError(
                f"You can only associate up to {max_num} images with this product."  # noqa: E501
            )


class CustumerRepresentativesInline(admin.TabularInline):
    model = CustumerRepresentatives
    formset = LimitCustumerRepresentatives
    extra = 1
    min_num = 1
    max_num = 10


class AdminCustumer(admin.ModelAdmin):
    inlines = [
        CustumerSubscriptionInline,
        CustumerDocsInline,
        CustumerRepresentativesInline,
    ]
    list_display = ["id", "full_name", "birth_date", "phone"]
    search_fields = ["id", "full_name", "birth_date", "phone"]


admin.site.register(Custumer, AdminCustumer)


class AdminCustumerSubscriptonPayment(admin.ModelAdmin):
    list_display = [
        "id",
        "custumer",
        "subscription",
        "summ",
        "summ_date",
        "sub_date",
        "cashier",
        "owner",
        "attendance_record",
    ]
    search_fields = [
        "id",
        "custumer__full_name",
        # "subscription",
        # "summ",
        # "summ_date",
        # "cashier",
        # "owner",
    ]
    list_filter = [
        "is_pay",
        "is_blok",
    ]


admin.site.register(
    CustumerSubscriptonPayment, AdminCustumerSubscriptonPayment
)
