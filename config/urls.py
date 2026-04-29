from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.urls")),
    path("news/", include("news.urls")),
    path("competitions/", include("competitions.urls")),
    path("market/", include("market.urls")),
    path("", include("authen.urls")),
    path("", include("achievements.urls")),
    path("", include("supervisor.urls")),
    path("", include("custumer.urls")),
    path("", include("employe.urls")),
    path("", include("groups_custumer.urls")),
    path("", include("group_classe.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {
            "document_root": settings.MEDIA_ROOT,
        },
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
