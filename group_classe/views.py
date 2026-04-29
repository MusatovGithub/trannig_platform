import re
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from custumer.models import Custumer
from employe.models import Employe
from employe.utils import get_user_permissions
from groups_custumer.models import (
    ClasessProgramm,
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)


# Groups Classess
@login_required
def group_classess(request):
    user = request.user

    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    user_permissions = get_user_permissions(user)

    # Проверяем все варианты прав доступа
    can_view_all_groups = "Может просматривать группы" in user_permissions
    can_view_own_groups = (
        "Может просматривать только свои группы" in user_permissions
    )
    can_view_classes = (
        "Может просматривать занятия только своих групп" in user_permissions
    )

    # Получаем экземпляр сотрудника
    try:
        employe_instance = Employe.objects.get(user=user)
    except Employe.DoesNotExist:
        employe_instance = None

    # Проверяем права доступа
    if not (
        is_admin
        or (
            is_assistant
            and (
                can_view_all_groups or can_view_own_groups or can_view_classes
            )
        )
    ):
        logout(request)
        return render(request, "page_404.html")

    # Полностью оптимизированный запрос с устранением N+1 проблем:
    # 1. select_related для ForeignKey (groups_id, employe, company, owner)
    # 2. prefetch_related для ClasessProgramm (item.classes.all в шаблоне)

    # Создаем Prefetch для программ занятий
    classes_programm_prefetch = Prefetch(
        "classes",  # related_name из модели ClasessProgramm
        queryset=ClasessProgramm.objects.order_by("id"),
    )

    classess_query = (
        GroupClasses.objects.filter(company=request.user.company)
        .select_related(
            "groups_id",  # Оптимизация ForeignKey для item.groups_id
            "employe",  # Оптимизация ForeignKey для тренера
            "company",  # Оптимизация ForeignKey
            "owner",  # Оптимизация ForeignKey
        )
        .prefetch_related(
            classes_programm_prefetch  # Оптимизация для item.classes.all
        )
        .order_by("-id")
    )

    # Фильтруем занятия в зависимости от прав
    if is_assistant and (can_view_own_groups or can_view_classes):
        if employe_instance:
            classess_query = classess_query.filter(
                groups_id__employe_id=employe_instance
            )
        else:
            logout(request)
            return render(request, "page_404.html")

    context = {}
    today = timezone.now().date()  # Bugungi sana

    date_filter = request.GET.get("date")

    if date_filter:
        try:
            # Stringdan datetime.date formatiga o'tkazish
            date_filter = datetime.strptime(date_filter, "%d.%m.%Y").date()
        except ValueError:
            date_filter = today  # Agar xato bo'lsa, bugungi sanani ishlatish
    else:
        date_filter = today

    # Sana detallari
    current_day = date_filter.day
    current_month = date_filter.month
    current_year = date_filter.year

    # Oldingi va keyingi kunlarni hisoblash
    previous_date = (date_filter - timedelta(days=1)).strftime(
        "%d.%m.%Y"
    )  # `YYYY-MM-DD`
    next_date = (date_filter + timedelta(days=1)).strftime(
        "%d.%m.%Y"
    )  # `YYYY-MM-DD`
    template = (
        "groups/classes/index.html"
        if is_admin
        else "groups/classes/assistent/index.html"
    )
    # Получаем права пользователя один раз для использования в шаблоне
    user_permissions_dict = {
        "can_create_classes": "Может добавлять занятие" in user_permissions,
        "can_edit_classes": "Может редактировать занятия" in user_permissions,
        "can_delete_classes": "Может удалять занятия" in user_permissions,
        "can_create_program": (
            "Может создавать программу тренировки" in user_permissions
        ),
        "can_edit_program": (
            "Может редактировать программу тренировки" in user_permissions
        ),
    }

    context.update(
        {
            "classess": classess_query.filter(date=date_filter),
            "date": date_filter,
            "current_day": current_day,
            "current_month": current_month,
            "current_year": current_year,
            "previous_date": previous_date,
            "next_date": next_date,
            "user_permissions": user_permissions_dict,
        }
    )

    return render(request, template, context)


@login_required
def group_classess_create(request):
    user = request.user

    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Default template
    template = (
        "groups/classes/create.html"
        if is_admin
        else "groups/classes/assistent/create.html"
    )

    user_permissions = get_user_permissions(user)
    can_create_classes = "Может добавлять занятие" in user_permissions

    if is_admin or (is_assistant and can_create_classes):
        context = {}
        # Оптимизированная загрузка - только нужные поля
        context["groups"] = GroupsClass.objects.filter(
            company=request.user.company
        ).only("id", "name")
        context["employe"] = Employe.objects.filter(
            company=request.user.company
        ).only("id", "full_name")

        if request.method == "POST":
            name = request.POST.get("name")
            groups_id = request.POST.get("groups_id")
            start_date_str = request.POST.get("start_date")
            strat = request.POST.get("strat")
            end = request.POST.get("end")
            employe = request.POST.get("employe")
            comment = request.POST.get("comment")

            if (
                not groups_id
                or not name
                or not start_date_str
                or not strat
                or not end
                or not employe
            ):
                context["error"] = (
                    "Пожалуйста, заполните все обязательные поля."
                )
            else:
                start_date = datetime.strptime(
                    start_date_str, "%d.%m.%Y"
                ).date()
                groups = get_object_or_404(GroupsClass, id=groups_id)
                empl = get_object_or_404(Employe, id=employe)
                custumers = Custumer.objects.filter(groups__id=groups.id)
                group_class = GroupClasses(
                    name=name,
                    groups_id=groups,
                    date=start_date,
                    strat=strat,
                    end=end,
                    employe=empl,
                    comment=comment,
                    company=request.user.company,
                    owner=request.user,
                    is_manual=True,
                )
                group_class.save()

                for custumer in custumers:
                    GroupClassessCustumer.objects.get_or_create(
                        gr_class=group_class,
                        custumer=custumer,
                        date=start_date,
                        defaults={
                            "company": request.user.company,
                            "owner": request.user,
                        },
                    )
                return redirect("group_classe:group_classess")

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def group_classess_update(request, pk):
    user = request.user

    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Default template
    template = (
        "groups/classes/update.html"
        if is_admin
        else "groups/classes/assistent/update.html"
    )

    user_permissions = get_user_permissions(user)
    can_edit_classes = "Может редактировать занятия" in user_permissions

    if is_admin or (is_assistant and can_edit_classes):
        context = {}
        # Оптимизированная загрузка - только нужные поля
        context["groups"] = GroupsClass.objects.filter(
            company=request.user.company
        ).only("id", "name")
        context["employe"] = Employe.objects.filter(
            company=request.user.company
        ).only("id", "full_name")
        # Используем get_object_or_404 вместо [0] для безопасности
        context["classess"] = get_object_or_404(GroupClasses, id=pk)

        if request.method == "POST":
            groups_id = request.POST.get("groups_id")
            start_date_str = request.POST.get("start_date")
            strat = request.POST.get("strat")
            end = request.POST.get("end")
            employe = request.POST.get("employe")
            comment = request.POST.get("comment")

            if (
                not groups_id
                or not start_date_str
                or not strat
                or not end
                or not employe
            ):
                context["error"] = (
                    "Пожалуйста, заполните все обязательные поля."
                )
            else:
                start_date = datetime.strptime(
                    start_date_str, "%d.%m.%Y"
                ).date()
                groups = get_object_or_404(GroupsClass, id=groups_id)
                empl = get_object_or_404(Employe, id=employe)
                classess = context["classess"]
                classess.groups_id = groups
                classess.date = start_date
                classess.strat = strat
                classess.end = end
                classess.employe = empl
                classess.comment = comment
                classess.save()
                return redirect("group_classe:group_classess")

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def group_classess_delete(request, pk):
    user = request.user

    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    user_permissions = get_user_permissions(user)
    can_delete_classes = "Может удалять занятия" in user_permissions

    if is_admin or (is_assistant and can_delete_classes):
        group = get_object_or_404(GroupClasses, id=pk)
        group.delete()
        return redirect("group_classe:group_classess")
    logout(request)
    return render(request, "page_404.html")


# Classess Programm
@login_required
def classes_programm_add(request, pk):
    user = request.user

    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Default template
    template = (
        "groups/classes/programm/create.html"
        if is_admin
        else "groups/classes/programm/create1.html"
    )

    user_permissions = get_user_permissions(user)
    can_add_program = (
        "Может создавать программу тренировки" in user_permissions
    )

    if is_admin or (is_assistant and can_add_program):
        context = {}
        context["classes"] = get_object_or_404(GroupClasses, id=pk)

        if request.method == "POST":
            stages = request.POST.getlist("stages")
            distances = request.POST.getlist("distance")
            styles = request.POST.getlist("style")
            rests = request.POST.getlist("rest")
            comments = request.POST.getlist("comment")

            error_messages = []

            for i in range(len(stages)):
                if not stages[i] or not distances[i]:
                    error_messages.append(
                        f"{i + 1}-Обязательные поля в строке не заполнены!"
                    )
                if "," in distances[i] or not re.match(
                    r"^\d+(\.\d+)?$", distances[i]
                ):
                    error_messages.append(
                        f"{i + 1}-Дистанция должна быть в метрах через точку, "
                        "например: 100.0"
                    )

            if error_messages:
                messages.error(request, " | ".join(error_messages))
                return render(request, template, context)

            # Agar xato bo'lmasa, ma'lumotlarni saqlaymiz
            data_to_save = [
                ClasessProgramm(
                    classes=context["classes"],
                    stages=stages[i],
                    distance=distances[i],
                    style=styles[i],
                    rest=rests[i],
                    comments=comments[i]
                    if comments[i]
                    else None,  # comment ixtiyoriy
                )
                for i in range(len(stages))
            ]
            ClasessProgramm.objects.bulk_create(data_to_save)

            return redirect("group_classe:group_classess")

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def classes_programm_update(request, pk):
    user = request.user

    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Default template
    template = (
        "groups/classes/programm/update.html"
        if is_admin
        else "groups/classes/programm/update1.html"
    )

    user_permissions = get_user_permissions(user)
    can_edit_program = (
        "Может редактировать программу тренировки" in user_permissions
    )

    if is_admin or (is_assistant and can_edit_program):
        # Оптимизированная загрузка с select_related для избежания N+1
        group_class = get_object_or_404(
            GroupClasses.objects.select_related("groups_id", "employe"), id=pk
        )
        class_programs = ClasessProgramm.objects.filter(
            classes=group_class
        ).order_by("id")

        if request.method == "POST":
            stages = request.POST.getlist("stages")
            distances = request.POST.getlist("distance")
            styles = request.POST.getlist("style")
            rests = request.POST.getlist("rest")
            comments = request.POST.getlist("comment")

            error_messages = []

            # Xatoliklarni tekshirish
            # (majburiy maydonlar bo'sh bo'lmasligi kerak)
            for i in range(len(stages)):
                if not stages[i] or not distances[i]:
                    error_messages.append(
                        f"{i + 1}-Обязательные поля в строке не заполнены!"
                    )

            if error_messages:
                messages.error(request, " | ".join(error_messages))
                return render(
                    request,
                    "groups/classes/programm/update.html",
                    {
                        "group_class": group_class,
                        "class_programs": class_programs,
                    },
                )  # Xatolik bo‘lsa, sahifa qayta yuklanadi

            # Eski yozuvlarni o‘chirib, yangi ma’lumotlarni saqlash
            class_programs.delete()

            new_programs = [
                ClasessProgramm(
                    classes=group_class,
                    stages=stages[i],
                    distance=distances[i],
                    style=styles[i],
                    rest=rests[i],
                    comments=comments[i]
                    if comments[i]
                    else None,  # comment ixtiyoriy
                )
                for i in range(len(stages))
            ]
            ClasessProgramm.objects.bulk_create(new_programs)

            return redirect("group_classe:group_classess")
        return render(
            request,
            template,
            {
                "group_class": group_class,
                "class_programs": class_programs,
            },
        )
    logout(request)
    return render(request, "page_404.html")
