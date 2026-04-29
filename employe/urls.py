from django.urls import path

from employe.roll.views import (
    employe_roll,
    employe_roll_create,
    employe_roll_delete,
    employe_roll_update,
)
from employe.views import (
    employe_create,
    employe_delete,
    employe_list,
    employe_send_message,
    employe_update,
)

app_name = "employe"

urlpatterns = [
    path("employe/all/", employe_list, name="employe_list"),
    path("employe/add/", employe_create, name="employe_create"),
    path("employe/update/<int:pk>/", employe_update, name="employe_update"),
    path("employe/delete/<int:pk>/", employe_delete, name="employe_delete"),
    path(
        "employe/send/message/<int:pk>/",
        employe_send_message,
        name="employe_send_message",
    ),
    # roll
    path("employe/roll/list/", employe_roll, name="employe_roll"),
    path("employe/roll/add/", employe_roll_create, name="employe_roll_create"),
    path(
        "employe/roll/update/<int:pk>/",
        employe_roll_update,
        name="employe_roll_update",
    ),
    path(
        "employe/roll/delete/<int:pk>/",
        employe_roll_delete,
        name="employe_roll_delete",
    ),
]
