from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from employe.models import (
    EmployePermissions,
    EmployePermissionsGroups,
    EmployeRoll,
)
from employe.utils import get_user_permissions


@login_required
def employe_roll(request):
    user = request.user

    # Оптимизированная проверка прав с использованием утилиты
    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Получаем права пользователя один раз
    user_permissions = get_user_permissions(user)
    can_view_roles = "Может просматривать роли" in user_permissions

    # Проверяем доступ
    if not (is_admin or (is_assistant and can_view_roles)):
        logout(request)
        return render(request, "page_404.html")

    # Оптимизированный запрос - уже есть prefetch_related для perm
    # Добавляем select_related для company и owner если нужно
    roll_list = (
        EmployeRoll.objects.filter(company=request.user.company)
        .select_related("company", "owner")  # Оптимизация ForeignKey
        .prefetch_related("perm")  # Оптимизация ManyToMany
        .order_by("-id")
    )

    template = "roll/index.html" if is_admin else "roll/assistent/index.html"

    context = {
        "roll_list": roll_list,
    }

    return render(request, template, context)


@login_required
def employe_roll_create(request):
    user = request.user

    # Оптимизированная проверка прав
    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Получаем права пользователя один раз
    user_permissions = get_user_permissions(user)
    can_add_roles = "Может добавлять роли" in user_permissions

    # Проверяем доступ
    if not (is_admin or (is_assistant and can_add_roles)):
        logout(request)
        return render(request, "page_404.html")

    template = "roll/create.html" if is_admin else "roll/assistent/create.html"

    # Полностью оптимизированная загрузка групп с правами
    # Устраняет N+1 для item.perm_group.all в шаблоне (строка 38)
    permissions_prefetch = Prefetch(
        "perm_group",  # related_name из EmployePermissions.group
        queryset=EmployePermissions.objects.order_by("id"),
    )

    groups = EmployePermissionsGroups.objects.prefetch_related(
        permissions_prefetch
    ).order_by("id")

    # Загружаем все права для отображения
    permissions = EmployePermissions.objects.select_related("group").order_by(
        "id"
    )

    context = {
        "groups": groups,
        "permissions": permissions,
    }

    if request.method == "POST":
        name = request.POST.get("name")
        permission_ids = request.POST.getlist("permission")

        if not name or not permission_ids:
            context["error"] = "Заполните все обязательные поля!"
            return render(request, template, context)

        roll = EmployeRoll.objects.create(
            name=name, company=request.user.company, owner=request.user
        )
        permissions_to_set = EmployePermissions.objects.filter(
            id__in=permission_ids
        )
        roll.perm.set(permissions_to_set)

        return redirect("employe:employe_roll")

    return render(request, template, context)


@login_required
def employe_roll_update(request, pk):
    user = request.user

    # Оптимизированная проверка прав
    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Получаем права пользователя один раз
    user_permissions = get_user_permissions(user)
    can_edit_roles = "Может изменять роли" in user_permissions

    # Проверяем доступ
    if not (is_admin or (is_assistant and can_edit_roles)):
        logout(request)
        return render(request, "page_404.html")

    template = "roll/update.html" if is_admin else "roll/assistent/update.html"

    # Оптимизированная загрузка роли с правами
    roll = get_object_or_404(
        EmployeRoll.objects.select_related(
            "company", "owner"
        ).prefetch_related("perm"),
        id=pk,
    )

    # Полностью оптимизированная загрузка групп с правами
    # Устраняет N+1 для item.perm_group.all в шаблоне
    permissions_prefetch = Prefetch(
        "perm_group",  # related_name из EmployePermissions.group
        queryset=EmployePermissions.objects.order_by("id"),
    )

    groups = EmployePermissionsGroups.objects.prefetch_related(
        permissions_prefetch
    ).order_by("id")

    # Загружаем все права для отображения
    permissions = EmployePermissions.objects.select_related("group").order_by(
        "id"
    )

    context = {
        "groups": groups,
        "permissions": permissions,
        "roll": roll,
    }

    if request.method == "POST":
        name = request.POST.get("name")
        permission_ids = request.POST.getlist("permission")

        if not name or not permission_ids:
            context["error"] = "Заполните все обязательные поля!"
            return render(request, template, context)

        roll.name = name
        roll.save()
        roll.perm.set(permission_ids)
        return redirect("employe:employe_roll")

    return render(request, template, context)


@login_required
def employe_roll_delete(request, pk):
    # Используем get_object_or_404 для безопасности
    roll = get_object_or_404(EmployeRoll, id=pk)
    roll.delete()
    return redirect("employe:employe_roll")
