from django.urls import path

from achievements.views import (
    achievement_create,
    achievement_list,
    achievement_update,
)

app_name = "achievements"

urlpatterns = [
    path("achievement/list/", achievement_list, name="achievement_list"),
    path("achievement/create/", achievement_create, name="achievement_create"),
    path(
        "achievement/update/<int:pk>/",
        achievement_update,
        name="achievement_update",
    ),
]
