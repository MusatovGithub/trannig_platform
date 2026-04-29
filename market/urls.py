from django.urls import path

from market.views import (
    create_product,
    delete_product,
    get_product_list,
    order_detail,
    order_list,
    sales_report,
    update_order_status,
    update_product,
)

app_name = "market"

urlpatterns = [
    path("", get_product_list, name="get_product_list"),
    path("create/", create_product, name="create_product"),
    path("<int:pk>/edit/", update_product, name="update_product"),
    path("<int:pk>/delete/", delete_product, name="delete_product"),
    # Заказы
    path("orders/", order_list, name="order_list"),
    path("orders/<int:pk>/", order_detail, name="order_detail"),
    path(
        "orders/<int:pk>/update-status/",
        update_order_status,
        name="update_order_status",
    ),
    path("sales-report/", sales_report, name="sales_report"),
]
