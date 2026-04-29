from django.urls import path

from group_classe.views import (
    classes_programm_add,
    classes_programm_update,
    group_classess,
    group_classess_create,
    group_classess_delete,
    group_classess_update,
)

app_name = "group_classe"

urlpatterns = [
    # Classess
    path("group/classes/", group_classess, name="group_classess"),
    path(
        "group/classes/create/",
        group_classess_create,
        name="group_classess_create",
    ),
    path(
        "group/classes/<int:pk>/update/",
        group_classess_update,
        name="group_classess_update",
    ),
    path(
        "group/classes/<int:pk>/detele/",
        group_classess_delete,
        name="group_classess_detele",
    ),
    # programm
    path(
        "classes/programm/add/<int:pk>/",
        classes_programm_add,
        name="classes_programm_add",
    ),
    path(
        "classes/programm/update/<int:pk>/",
        classes_programm_update,
        name="classes_programm_update",
    ),
]
