from django.urls import path

from news.views import news_create, news_delete, news_list, news_update

app_name = "news"

urlpatterns = [
    path("", news_list, name="news_list"),
    path("create/", news_create, name="news_create"),
    path("<int:pk>/edit/", news_update, name="news_update"),
    path("<int:pk>/delete/", news_delete, name="news_delete"),
]
