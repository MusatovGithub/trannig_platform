from django.core.cache import cache

from employe.models import EmployePermissions


class EmployePermissionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cache_key = "employe_permissions_all"
        permission_all = cache.get(cache_key)

        if permission_all is None:
            permission_all = list(EmployePermissions.objects.all())
            # Кешируем на 1 час в Redis
            cache.set(cache_key, permission_all, 3600)

        request.permission_all = permission_all
        response = self.get_response(request)
        return response
