from django.urls import path

from groups_custumer.views import (
    get_attendance_modal,
    get_customer_attendance_summary,
    get_or_create_attendance,
    group_subscription_create,
    groups_all,
    groups_classess_add,
    groups_create,
    groups_custumer_create,
    groups_delete,
    groups_detail,
    groups_detail_date,
    groups_update,
    mark_attendance,
    mark_attendance_ajax,
    mark_attendance_date,
    type_sport,
    type_sport_create,
    type_sport_delete,
    type_sport_update,
)

app_name = "groups_custumer"

urlpatterns = [
    path("groups/all/", groups_all, name="groups_all"),
    path("groups/add/", groups_create, name="groups_create"),
    path("groups/update/<int:pk>/", groups_update, name="groups_update"),
    path("groups/detail/<int:pk>/", groups_detail, name="groups_detail"),
    path(
        "groups/<int:pk>/date/<str:selected_date>/",
        groups_detail_date,
        name="groups_detail_with_date",
    ),
    path("groups/delete/<int:pk>/", groups_delete, name="groups_delete"),
    path(
        "group/<int:pk>/custumers/create/",
        groups_custumer_create,
        name="groups_custumer_create",
    ),
    path(
        "group/<int:group_id>/custumer/<int:custumer_id>/subscription/",
        group_subscription_create,
        name="group_subscription_create",
    ),
    # Classess
    path(
        "group/<int:pk>/classes/add/",
        groups_classess_add,
        name="groups_classess_add",
    ),
    # AJAX endpoint для выставления оценок
    path(
        "group/attendance/<int:attendance_id>/ajax/",
        mark_attendance_ajax,
        name="mark_attendance_ajax",
    ),
    # AJAX endpoint для загрузки модального окна
    path(
        "group/attendance/<int:attendance_id>/modal/",
        get_attendance_modal,
        name="get_attendance_modal",
    ),
    path(
        "group/<int:group_id>/customer/<int:customer_id>/summary/",
        get_customer_attendance_summary,
        name="get_customer_attendance_summary",
    ),
    # AJAX endpoint для получения или создания attendance
    path(
        "group/attendance/get-or-create/",
        get_or_create_attendance,
        name="get_or_create_attendance",
    ),
    # Старые endpoints для обратной совместимости
    path(
        (
            "group/<int:group_id>/custumer/<int:custumer_id>/"
            "attendance/<str:day_date>/<int:pk>/"
        ),
        mark_attendance,
        name="mark_attendance",
    ),
    path(
        (
            "group/<int:group_id>/custumer/<int:custumer_id>/"
            "attendance/<str:day_date>/<int:pk>/date/"
        ),
        mark_attendance_date,
        name="mark_attendance_date",
    ),
    path("group/type/sport/", type_sport, name="type_sport"),
    path(
        "group/type/sport/create/", type_sport_create, name="type_sport_create"
    ),
    path(
        "group/type/sport/update/<int:pk>/",
        type_sport_update,
        name="type_sport_update",
    ),
    path(
        "group/type/sport/delete/<int:pk>/",
        type_sport_delete,
        name="type_sport_delete",
    ),
]
