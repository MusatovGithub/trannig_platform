from django.urls import path

from authen.views import (
    change_password,
    change_password_client,
    change_profile,
    change_profile_assistent,
    change_profile_client,
    force_password_change,
    forget_password,
    logout_user,
    reset_passwords,
    sign_in,
    sign_up,
)

urlpatterns = [
    path("", sign_in, name="sign_in"),
    path("regsiter/", sign_up, name="sign_up"),
    path("logout_user/", logout_user, name="logout_user"),
    path("forget/password", forget_password, name="forget_password"),
    path(
        "reset/password/<str:reset_token>/",
        reset_passwords,
        name="reset_passwords",
    ),
    path("change/password/", change_password, name="change_password"),
    path("change/profile/", change_profile, name="change_profile"),
    path(
        "change/profile/assistent/",
        change_profile_assistent,
        name="change_profile_assistent",
    ),
    path(
        "change/profile/client/",
        change_profile_client,
        name="change_profile_client",
    ),
    path(
        "change/password/client/",
        change_password_client,
        name="change_password_client",
    ),
    path(
        "force/password/change/",
        force_password_change,
        name="force_password_change",
    ),
]
