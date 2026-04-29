from django.contrib import admin
from django.utils.html import format_html

from market.models import Cart, Order, OrderItem, Product, Purchase


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "owner", "get_sport_category_short")
    list_filter = ("sport_category", "owner")
    search_fields = ("name", "description")

    def get_sport_category_short(self, obj):
        """Отображает сокращенное название разряда в админке."""
        if obj.sport_category:
            return obj.sport_category.get_short_name()
        return "Без ограничений"

    get_sport_category_short.short_description = "Разряд"
    fieldsets = (
        (
            "Основная информация",
            {"fields": ("name", "description", "image", "price", "owner")},
        ),
        (
            "Ограничения",
            {
                "fields": ("sport_category",),
                "description": (
                    "Если указан разряд, товар могут купить только клиенты с "
                    "этим разрядом или выше"
                ),
            },
        ),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "status",
        "total_amount",
        "created_at",
        "get_status_badge",
    )
    list_filter = ("status", "created_at", "customer")
    search_fields = ("customer__username", "customer__email", "id")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    def get_status_badge(self, obj):
        color = obj.get_status_color()
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display(),
        )

    get_status_badge.short_description = "Статус"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("total_price",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price", "total_price")
    list_filter = ("order__status", "order__created_at")
    search_fields = ("order__id", "product__name")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("owner", "product", "purchased_at", "order")
    list_filter = ("purchased_at", "order__status")
    search_fields = ("owner__username", "product__name")
    date_hierarchy = "purchased_at"


admin.site.register(Cart)
