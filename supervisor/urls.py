from django.urls import path

from supervisor.views import home_client, home_employe, supervisor_home

app_name = "supervisor"

urlpatterns = [
    path("cabinet/", supervisor_home, name="cabinet"),
    path("home/", home_employe, name="home_epmloye"),
    path("home/client/", home_client, name="home_client"),
]
