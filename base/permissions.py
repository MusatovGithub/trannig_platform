from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if (
            not request.user.is_authenticated
            or not request.user.groups.filter(name="admin").exists()
        ):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def admin_or_assistant_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not (
            request.user.groups.filter(name="admin").exists()
            or request.user.groups.filter(name="assistant").exists()
        ):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped_view
