from calendar import monthrange
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from authen.models import TypeSportsCompany
from base.cache_utils import (
    get_cached_company_employees,
    get_cached_type_sports,
    get_cached_weeks,
)
from custumer.models import (
    Custumer,
    CustumerSubscription,
)
from custumer.payment.services import get_unpaid_count_for_customer_in_group
from custumer.subscription.services import (
    ensure_can_add_subscription,
    prepare_subscription_form_context,
    process_subscription_submission,
)
from employe.models import Employe
from employe.utils import get_user_permissions
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
    Schedule,
)
from groups_custumer.services import (
    AttendanceBlockedError,
    AttendanceValidationError,
    DateParseError,
    GroupValidationError,
    ScheduleValidationError,
    assign_coaches,
    create_group,
    create_group_classes_bulk,
    create_schedules_bulk,
    delete_old_schedule_and_classes,
    generate_group_classes,
    get_attendance_css_class,
    get_attendance_display_text,
    preserve_attendance_data,
    process_attendance_mark,
    restore_attendance_data,
    update_customer_balance,
    update_group,
    validate_end_date,
    validate_group_data,
    validate_schedule_data,
)

ATTENDANCE_GRADE_STATUSES = [
    "attended_2",
    "attended_3",
    "attended_4",
    "attended_5",
    "attended_10",
]


def _check_user_permissions(user, permission_func=None):
    """
    Оптимизированная проверка прав пользователя.

    Args:
        user: Пользователь для проверки
        permission_func: Функция для проверки конкретного права

    Returns:
        tuple: (is_admin, is_assistant, has_permission)
    """
    # Кешируем группы пользователя для избежания повторных запросов
    if not hasattr(user, "_cached_groups"):
        user._cached_groups = list(user.groups.values_list("name", flat=True))

    user_groups = user._cached_groups
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    if permission_func and is_assistant:
        has_permission = permission_func(user)
    else:
        has_permission = is_admin

    return is_admin, is_assistant, has_permission


@transaction.atomic
def update_balance_on_attendance(custumer, old_status, new_status):
    """
    Обёртка для обратной совместимости.
    Использует update_customer_balance из сервисного слоя.
    """
    update_customer_balance(custumer, old_status, new_status)


@login_required
def groups_all(request):
    user = request.user
    search_query = request.GET.get("search", "")
    employe_id = request.GET.get("employe_id", "")
    company = user.company
    page = int(request.GET.get("page", 1))
    per_page = 10
    # Foydalanuvchi admin yoki assistantligini tekshiramiz
    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Получаем права пользователя один раз
    user_permissions = get_user_permissions(user)
    can_view_all_groups = "Может просматривать группы" in user_permissions
    can_view_own_groups = (
        "Может просматривать только свои группы" in user_permissions
    )

    # Foydalanuvchini `Employe` modeliga bog'lash
    try:
        employe_instance = Employe.objects.get(user=user)
    except Employe.DoesNotExist:
        employe_instance = None

    if is_admin or (
        is_assistant and (can_view_all_groups or can_view_own_groups)
    ):
        # Полностью оптимизированный запрос с устранением N+1 проблем:
        # 1. Prefetch для Schedule с select_related для Week
        #    (устраняет N+1 на schedule.week)
        # 2. select_related для type_sport (если нужно в шаблоне)
        # 3. prefetch_related для employe_id (ManyToMany)
        # 4. annotate для подсчета клиентов

        # Создаем оптимизированный Prefetch для расписания
        # с загрузкой Week. Используем Prefetch без to_attr,
        # чтобы Django автоматически кешировал для groups.all
        schedule_prefetch = Prefetch(
            "groups",  # related_name из модели Schedule
            queryset=Schedule.objects.select_related("week").order_by(
                "week__id", "strat_time"
            ),
        )

        groups_qs = (
            GroupsClass.objects.filter(company=company)
            .select_related("type_sport")  # Оптимизация ForeignKey
            .prefetch_related(
                schedule_prefetch,  # Оптимизированная загрузка
                "employe_id",  # ManyToMany связь с тренерами
            )
            .annotate(
                custumer_count=Count("custumer", distinct=True)
            )  # Подсчитываем клиентов
            .order_by("-id")
        )

        # Agar assistant faqat o'z guruhlarini ko'ra olsa,
        # employe_id bilan filtrlaymiz
        if (
            is_assistant
            and can_view_own_groups
            and not can_view_all_groups
            and employe_instance
        ):
            groups_qs = groups_qs.filter(employe_id=employe_instance)

        if search_query:
            groups_qs = groups_qs.filter(
                Q(name__icontains=search_query)
                | Q(strat_training__icontains=search_query)
            )

        if employe_id:
            groups_qs = groups_qs.filter(employe_id=employe_id)

        paginator = Paginator(groups_qs, per_page)
        page_obj = paginator.get_page(page)

        template = (
            "groups/index.html" if is_admin else "employe/groups/index.html"
        )

        # Подготавливаем права для шаблона
        user_permissions_dict = {
            "can_create_groups": "Может добавлять группы" in user_permissions,
            "can_edit_groups": "Может редактировать группы"
            in user_permissions,
            "can_delete_groups": "Может удалять группы" in user_permissions,
        }

        # Оптимизированная загрузка сотрудников - только нужные поля
        employes_list = (
            Employe.objects.filter(company=company)
            .only("id", "full_name")
            .order_by("-id")
        )

        context = {
            "employes": employes_list,
            "groups": page_obj,
            "search_query": search_query,
            "selected_employe_id": employe_id,
            "user_permissions": user_permissions_dict,
            "page_obj": page_obj,
        }
        return render(request, template, context)

    logout(request)
    return render(request, "page_404.html")


WEEKDAY_TRANSLATION = {
    "Monday": "Понедельник",
    "Tuesday": "Вторник",
    "Wednesday": "Среда",
    "Thursday": "Четверг",
    "Friday": "Пятница",
    "Saturday": "Суббота",
    "Sunday": "Воскресенье",
}


@login_required
@transaction.atomic
def groups_create(request):
    user = request.user

    template = (
        "groups/create.html"
        if user.groups.filter(name="admin").exists()
        else "employe/groups/create.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может добавлять группы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        company_id = request.user.company.id
        context = {
            "employes": get_cached_company_employees(company_id),
            "weeks": get_cached_weeks(),
            "type_sports": get_cached_type_sports(company_id),
        }

        if request.method == "POST":
            try:
                # Получение данных из POST
                name = request.POST.get("name")
                sport_type_id = request.POST.get("sport_type")
                coaches_ids = request.POST.getlist("coaches")
                start_date_str = request.POST.get("start_date")
                name_schedule = request.POST.getlist("name_schedule[]")
                weeks_data = request.POST.getlist("weeks[]")
                time_start = request.POST.getlist("time_strat")
                time_end = request.POST.getlist("time_end")
                end_date_str = request.POST.get("end_date", None)

                # Валидация основных данных группы
                validated_data = validate_group_data(
                    name,
                    sport_type_id,
                    coaches_ids,
                    start_date_str,
                    user.company,
                )
                name, sport_type, coaches, start_date = validated_data
                end_date = validate_end_date(end_date_str, start_date)

                # Создание группы
                group = create_group(
                    name, sport_type, start_date, end_date, user.company, user
                )

                # Назначение тренеров
                assign_coaches(group, coaches)

                # Валидация данных расписания
                validated_schedules = validate_schedule_data(
                    name_schedule, weeks_data, time_start, time_end
                )

                if validated_schedules:
                    # Массовое создание расписаний
                    create_schedules_bulk(group, validated_schedules)

                    # Генерация и создание занятий
                    classes_objects = generate_group_classes(
                        group,
                        validated_schedules,
                        start_date,
                        end_date,
                        user.company,
                        user,
                    )
                    created_classes = create_group_classes_bulk(
                        classes_objects
                    )

                    # Создание записей посещаемости для существующих клиентов
                    customers = group.custumer_set.all()
                    if customers.exists() and created_classes:
                        # Используем bulk_create для оптимизации
                        from groups_custumer.services.schedule_service import (
                            create_attendance_records_bulk,
                        )

                        create_attendance_records_bulk(
                            created_classes, customers, user.company, user
                        )

                return redirect("groups_custumer:groups_all")

            except GroupValidationError as e:
                context["error"] = str(e)
            except ScheduleValidationError as e:
                context["error"] = str(e)
            except DateParseError as e:
                context["error"] = str(e)
            except Exception as e:
                context["error"] = f"Произошла непредвиденная ошибка: {str(e)}"

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
@transaction.atomic
def groups_update(request, pk):
    user = request.user

    # Default template
    template = (
        "groups/update.html"
        if user.groups.filter(name="admin").exists()
        else "employe/groups/update.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может редактировать группы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        group = get_object_or_404(GroupsClass, id=pk)
        company_id = request.user.company.id
        context = {
            "groups": group,
            "employes": get_cached_company_employees(company_id),
            "weeks": get_cached_weeks(),
            "type_sports": get_cached_type_sports(company_id),
        }

        if request.method == "POST":
            try:
                # Получение данных из POST
                name = request.POST.get("name")
                sport_type_id = request.POST.get("sport_type")
                coaches_ids = request.POST.getlist("coaches")
                start_date_str = request.POST.get("start_date")
                name_schedule = request.POST.getlist("name_schedule[]")
                weeks_data = request.POST.getlist("weeks[]")
                time_start = request.POST.getlist("time_strat")
                time_end = request.POST.getlist("time_end")
                end_date_str = request.POST.get("end_date", None)

                # Валидация основных данных группы
                validated_data = validate_group_data(
                    name,
                    sport_type_id,
                    coaches_ids,
                    start_date_str,
                    user.company,
                )
                name, sport_type, coaches, start_date = validated_data
                end_date = validate_end_date(end_date_str, start_date)

                # Сохранение существующих данных посещаемости
                attendance_map = preserve_attendance_data(group)

                # Обновление основных полей группы
                update_group(group, name, sport_type, start_date, end_date)

                # Обновление тренеров
                assign_coaches(group, coaches)

                # Удаление старого расписания и занятий
                delete_old_schedule_and_classes(group)

                # Валидация данных расписания
                validated_schedules = validate_schedule_data(
                    name_schedule, weeks_data, time_start, time_end
                )

                if validated_schedules:
                    # Массовое создание расписаний
                    create_schedules_bulk(group, validated_schedules)

                    # Генерация и создание занятий
                    classes_objects = generate_group_classes(
                        group,
                        validated_schedules,
                        start_date,
                        end_date,
                        user.company,
                        user,
                    )
                    created_classes = create_group_classes_bulk(
                        classes_objects
                    )

                    # Восстановление данных посещаемости
                    customers = group.custumer_set.all()
                    if created_classes:
                        restore_attendance_data(
                            created_classes,
                            attendance_map,
                            customers,
                            user.company,
                            user,
                        )

                return redirect("groups_custumer:groups_all")

            except GroupValidationError as e:
                context["error"] = str(e)
            except ScheduleValidationError as e:
                context["error"] = str(e)
            except DateParseError as e:
                context["error"] = str(e)
            except Exception as e:
                context["error"] = f"Произошла непредвиденная ошибка: {str(e)}"

        return render(request, template, context)

    logout(request)
    return render(request, "page_404.html")


@login_required
def groups_delete(request, pk):
    groups = GroupsClass.objects.get(id=pk)
    groups.delete()
    return redirect("groups_custumer:groups_all")


@login_required
@transaction.atomic
def mark_attendance_ajax(request, attendance_id):
    """
    AJAX-обработчик для выставления оценок без перезагрузки страницы.

    Args:
        request: HTTP запрос
        attendance_id: ID записи посещаемости

    Returns:
        JsonResponse с результатом операции
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Метод не поддерживается"}, status=405
        )

    try:
        # Получение данных из запроса
        status = request.POST.get("status")
        comment = request.POST.get("comment")

        if not status:
            return JsonResponse(
                {"success": False, "error": "Статус не указан"}, status=400
            )

        # Получение записи посещаемости с оптимизацией запросов
        # Используем select_related для предзагрузки всех связанных объектов
        # и prefetch_related для предзагрузки подписок клиента с их группами
        attendance = get_object_or_404(
            GroupClassessCustumer.objects.select_related(
                "custumer",
                "custumer__gender",
                "custumer__company",
                "custumer__owner",
                "gr_class",
                "gr_class__groups_id",
                "gr_class__groups_id__company",
                "gr_class__groups_id__type_sport",
                "gr_class__employe",
                "gr_class__company",
                "gr_class__owner",
                "used_subscription",
                "used_subscription__custumer",
                "used_subscription__company",
                "used_subscription__owner",
                "company",
                "owner",
            ).prefetch_related(
                Prefetch(
                    "custumer__custumersubscription_set",
                    queryset=CustumerSubscription.objects.select_related(
                        "custumer", "company", "owner"
                    )
                    .prefetch_related("groups")
                    .order_by("start_date"),
                    to_attr="prefetched_subscriptions",
                )
            ),
            id=attendance_id,
        )

        # Обработка через сервисный слой
        result = process_attendance_mark(
            attendance=attendance,
            new_status=status,
            comment=comment,
            company=request.user.company,
            owner=request.user,
        )

        # Добавление данных для UI
        result["display_text"] = get_attendance_display_text(status)
        result["css_class"] = get_attendance_css_class(status)

        action_messages = {
            "set_grade": "Оценка успешно сохранена",
            "set_absent": 'Отметка "Не был" сохранена',
            "reset": "Оценка удалена",
        }
        result["message"] = action_messages.get(
            result.get("action"), "Изменения успешно сохранены"
        )

        return JsonResponse(result)

    except AttendanceValidationError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except AttendanceBlockedError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Ошибка сервера: {str(e)}"},
            status=500,
        )


@login_required
def get_attendance_modal(request, attendance_id):
    """
    Возвращает HTML модального окна для конкретной записи посещаемости.
    Загружается динамически по AJAX для оптимизации производительности.
    """
    try:
        # Получаем attendance с предзагрузкой custumer
        attendance = get_object_or_404(
            GroupClassessCustumer.objects.select_related(
                "custumer",
                "gr_class",
                "gr_class__groups_id",
                "company",
                "owner",
            ),
            id=attendance_id,
        )

        # Рендерим только содержимое модального окна
        html = render_to_string(
            "groups/includes/attendance_modal_content.html",
            {"attend": attendance},
            request=request,
        )

        return JsonResponse(
            {
                "html": html,
                "customer_name": attendance.custumer.full_name,
                "attendance_id": attendance.id,
            }
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Ошибка загрузки: {str(e)}"}, status=500
        )


@login_required
def get_or_create_attendance(request):
    """
    Получает или создает запись посещаемости для gr_class и custumer.
    Используется для пустых ячеек в мобильной версии.
    """
    try:
        gr_class_id = request.GET.get("gr_class_id")
        custumer_id = request.GET.get("custumer_id")
        date_str = request.GET.get("date")

        if not gr_class_id or not custumer_id:
            return JsonResponse(
                {"error": "Не указаны gr_class_id или custumer_id"}, status=400
            )

        # Получаем gr_class
        gr_class = get_object_or_404(GroupClasses, id=gr_class_id)

        # Получаем custumer
        custumer = get_object_or_404(Custumer, id=custumer_id)

        # Определяем дату
        if date_str:
            try:
                attendance_date = datetime.strptime(
                    date_str, "%Y-%m-%d"
                ).date()
            except ValueError:
                attendance_date = gr_class.date
        else:
            attendance_date = gr_class.date

        # Получаем или создаем attendance
        attendance, created = GroupClassessCustumer.objects.get_or_create(
            gr_class=gr_class,
            custumer=custumer,
            date=attendance_date,
            defaults={
                "attendance_status": "none",
                "company": request.user.company,
                "owner": request.user,
            },
        )

        return JsonResponse(
            {
                "attendance_id": attendance.id,
                "created": created,
            }
        )

    except Exception as e:
        return JsonResponse({"error": f"Ошибка: {str(e)}"}, status=500)


@login_required
@transaction.atomic
def mark_attendance(request, group_id, custumer_id, day_date, pk):
    """
    Обработчик выставления оценок с редиректом (для обратной совместимости).
    Использует сервисный слой для бизнес-логики.
    """
    group = get_object_or_404(GroupsClass, id=group_id)
    custumer = get_object_or_404(Custumer, id=custumer_id)

    try:
        day_date = datetime.strptime(day_date, "%Y-%m-%d").date()
    except ValueError as e:
        return HttpResponseBadRequest(
            f"Ошибка: неверный формат даты ({day_date}). Ошибка: {str(e)}"
        )

    gr_class = GroupClasses.objects.filter(
        groups_id=group, date=day_date
    ).first()
    if not gr_class:
        return HttpResponseBadRequest("Отсутствует занятие на эту дату")

    attendense = GroupClassessCustumer.objects.filter(
        id=pk,
        custumer=custumer,
        gr_class__groups_id=group_id,
        date=day_date,
    ).first()

    if not attendense:
        return redirect(
            "groups_custumer:group_subscription_create",
            group_id=group.id,
            custumer_id=custumer.id,
        )

    # Получение данных из запроса
    status = request.POST.get("status") or request.GET.get("status")
    comment = request.POST.get("comment")

    if not status:
        return HttpResponseBadRequest("Статус не указан")

    try:
        # Обработка через сервисный слой
        process_attendance_mark(
            attendance=attendense,
            new_status=status,
            comment=comment,
            company=request.user.company,
            owner=request.user,
        )
        return redirect("groups_custumer:groups_detail", pk=group_id)

    except AttendanceBlockedError as e:
        messages.error(request, str(e))
        return redirect("groups_custumer:groups_detail", pk=group_id)
    except (AttendanceValidationError, ValueError) as e:
        messages.error(request, str(e))
        return redirect("groups_custumer:groups_detail", pk=group_id)


@login_required
@transaction.atomic
def mark_attendance_date(request, group_id, custumer_id, day_date, pk):
    """
    Обработчик выставления оценок с редиректом для конкретной даты.
    Использует сервисный слой для бизнес-логики.
    """
    group = get_object_or_404(GroupsClass, id=group_id)
    custumer = get_object_or_404(Custumer, id=custumer_id)

    try:
        day_date = datetime.strptime(day_date, "%Y-%m-%d").date()
    except ValueError as e:
        return HttpResponseBadRequest(
            f"Xatolik: noto'g'ri sana formati ({day_date}). Xatolik: {str(e)}"
        )

    gr_class = GroupClasses.objects.filter(
        groups_id=group, date=day_date
    ).first()
    if not gr_class:
        return HttpResponseBadRequest(
            "Xatolik: Ushbu sana uchun dars mavjud emas."
        )

    attendense = GroupClassessCustumer.objects.filter(
        id=pk,
        custumer=custumer,
        gr_class__groups_id=group_id,
        date=day_date,
    ).first()

    if not attendense:
        return redirect(
            "groups_custumer:group_subscription_create",
            group_id=group.id,
            custumer_id=custumer.id,
        )

    # Получение данных из запроса
    status = request.POST.get("status") or request.GET.get("status")
    comment = request.POST.get("comment")

    if not status:
        return HttpResponseBadRequest("Статус не указан")

    try:
        # Обработка через сервисный слой
        process_attendance_mark(
            attendance=attendense,
            new_status=status,
            comment=comment,
            company=request.user.company,
            owner=request.user,
        )
        return redirect(
            "groups_custumer:groups_detail_with_date",
            pk=group_id,
            selected_date=day_date,
        )

    except AttendanceBlockedError as e:
        messages.error(request, str(e))
        return redirect(
            "groups_custumer:groups_detail_with_date",
            pk=group_id,
            selected_date=day_date,
        )
    except (AttendanceValidationError, ValueError) as e:
        messages.error(request, str(e))
        return redirect(
            "groups_custumer:groups_detail_with_date",
            pk=group_id,
            selected_date=day_date,
        )


@login_required
def groups_detail(request, pk):
    user = request.user
    is_admin, is_assistant, _ = _check_user_permissions(user)

    # Получаем все права пользователя одним запросом
    user_permissions = get_user_permissions(user)

    can_view_all_groups = "Может просматривать группы" in user_permissions
    can_view_own_groups = (
        "Может просматривать только свои группы" in user_permissions
    )
    can_view_classes = (
        "Может просматривать занятия только своих групп" in user_permissions
    )

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
        return render(request, "page_404.html")

    group = get_object_or_404(GroupsClass, id=pk)

    # Если ассистент может видеть только свои группы или занятия, проверяем
    if is_assistant and (can_view_own_groups or can_view_classes):
        try:
            employe_instance = Employe.objects.get(user=user)
            # Проверяем, что группа принадлежит этому сотруднику
            # Проверка через связь многие-ко-многим в модели GroupsClass
            if not group.employe_id.filter(id=employe_instance.id).exists():
                return render(request, "page_404.html")
        except Employe.DoesNotExist:
            return render(request, "page_404.html")

    if is_admin or (
        is_assistant
        and (can_view_all_groups or can_view_own_groups or can_view_classes)
    ):
        year = int(request.GET.get("year", date.today().year))
        month = int(request.GET.get("month", date.today().month))

        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        group_classes = list(
            GroupClasses.objects.filter(
                groups_id=group, date__range=(first_day, last_day)
            )
            .only("id", "date", "strat", "end", "name")
            .order_by("date", "strat")
        )

        calendar_days = [(gc.date, gc.name) for gc in group_classes]
        prev_month = (first_day - timedelta(days=1)).replace(day=1)
        next_month = (last_day + timedelta(days=1)).replace(day=1)

        customers = list(
            Custumer.objects.filter(groups=group)
            .only("id", "full_name", "is_none")
            .order_by("full_name")
        )

        attendance_qs = GroupClassessCustumer.objects.filter(
            gr_class__groups_id=group, date__range=(first_day, last_day)
        ).only("id", "custumer_id", "gr_class_id", "attendance_status")

        attendance_lookup = {
            (att.custumer_id, att.gr_class_id): att for att in attendance_qs
        }

        attendance_display = {
            "attended_2": {"text": "2", "css": "grade-2"},
            "attended_3": {"text": "3", "css": "grade-3"},
            "attended_4": {"text": "4", "css": "grade-4"},
            "attended_5": {"text": "5", "css": "grade-5"},
            "attended_10": {"text": "10", "css": "grade-10"},
            "not_attended": {"text": "Н", "css": "status-absent"},
            "none": {"text": "+", "css": "status-empty"},
        }

        custumer_data = []
        for customer in customers:
            if customer.is_none:
                continue

            attendance_cells = []
            for gr_class in group_classes:
                attendance = attendance_lookup.get((customer.id, gr_class.id))
                if attendance:
                    display = attendance_display.get(
                        attendance.attendance_status,
                        {"text": "+", "css": "status-empty"},
                    )
                    attendance_cells.append(
                        {
                            "id": attendance.id,
                            "text": display["text"],
                            "css": display["css"],
                            "has_data": True,
                            "date": gr_class.date,
                            "date_name": gr_class.name or "",
                            "gr_class_id": gr_class.id,
                        }
                    )
                else:
                    attendance_cells.append(
                        {
                            "id": None,
                            "text": "+",
                            "css": "status-empty",
                            "has_data": False,
                            "date": gr_class.date,
                            "date_name": gr_class.name or "",
                            "gr_class_id": gr_class.id,
                        }
                    )

            custumer_data.append(
                {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "attendance_cells": attendance_cells,
                }
            )

        employee_permissions = {}
        if is_assistant:
            employee_permissions = {
                "can_add_customers": (
                    "Может добавлять клиентов" in user_permissions
                ),
                "can_add_classes": (
                    "Может добавлять занятия" in user_permissions
                ),
                "can_add_subscriptions": (
                    "Может добавлять Абонементы" in user_permissions
                ),
                "can_mark_attendance": (
                    "Может добавлять отметки посещаемости" in user_permissions
                ),
            }
        else:
            employee_permissions = {
                "can_add_customers": True,
                "can_add_classes": True,
                "can_add_subscriptions": True,
                "can_mark_attendance": True,
            }

        template = (
            "groups/detail.html" if is_admin else "employe/groups/detail.html"
        )

        context = {
            "group": group,
            "calendar_days": calendar_days,
            "current_year": year,
            "current_month": month,
            "prev_month": prev_month,
            "next_month": next_month,
            "group_classes": group_classes,
            "custumer_data": custumer_data,
            "employee_permissions": employee_permissions,
        }

        return render(request, template, context)
    return render(request, "page_404.html")


@login_required
def groups_detail_date(request, pk, selected_date=None):
    user = request.user
    is_admin, is_assistant, _ = _check_user_permissions(user)

    user_permissions = get_user_permissions(user)

    can_view_all_groups = "Может просматривать группы" in user_permissions
    can_view_own_groups = (
        "Может просматривать только свои группы" in user_permissions
    )
    can_view_classes = (
        "Может просматривать занятия только своих групп" in user_permissions
    )

    if not (
        is_admin
        or (
            is_assistant
            and (
                can_view_all_groups or can_view_own_groups or can_view_classes
            )
        )
    ):
        return render(request, "page_404.html")

    group = get_object_or_404(GroupsClass, id=pk)

    if is_assistant and (can_view_own_groups or can_view_classes):
        try:
            employe_instance = Employe.objects.get(user=user)
            if not group.employe_id.filter(id=employe_instance.id).exists():
                return render(request, "page_404.html")
        except Employe.DoesNotExist:
            return render(request, "page_404.html")

    if selected_date:
        try:
            selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            return render(request, "page_404.html")
    else:
        selected_date = date.today()

    group_classes = list(
        GroupClasses.objects.filter(groups_id=group, date=selected_date)
        .only("id", "date", "strat", "end", "name")
        .order_by("date", "strat")
    )
    calendar_days = [(gc.date, gc.name) for gc in group_classes]

    prev_day = selected_date - timedelta(days=1)
    next_day = selected_date + timedelta(days=1)

    customers = list(
        Custumer.objects.filter(groups=group)
        .only("id", "full_name", "is_none")
        .order_by("full_name")
    )

    attendance_qs = GroupClassessCustumer.objects.filter(
        gr_class__groups_id=group,
        date=selected_date,
    ).only("id", "custumer_id", "gr_class_id", "attendance_status")

    attendance_lookup = {
        (attendance.custumer_id, attendance.gr_class_id): attendance
        for attendance in attendance_qs
    }

    attendance_display = {
        "attended_2": {"text": "2", "css": "grade-2"},
        "attended_3": {"text": "3", "css": "grade-3"},
        "attended_4": {"text": "4", "css": "grade-4"},
        "attended_5": {"text": "5", "css": "grade-5"},
        "attended_10": {"text": "10", "css": "grade-10"},
        "not_attended": {"text": "Н", "css": "status-absent"},
        "none": {"text": "+", "css": "status-empty"},
    }

    custumer_data = []
    for customer in customers:
        if customer.is_none:
            continue

        attendance_cells = []
        for gr_class in group_classes:
            attendance = attendance_lookup.get((customer.id, gr_class.id))
            if attendance:
                display = attendance_display.get(
                    attendance.attendance_status,
                    {"text": "+", "css": "status-empty"},
                )
                attendance_cells.append(
                    {
                        "id": attendance.id,
                        "text": display["text"],
                        "css": display["css"],
                        "has_data": True,
                        "date": gr_class.date,
                        "date_name": gr_class.name or "",
                        "gr_class_id": gr_class.id,
                    }
                )
            else:
                attendance_cells.append(
                    {
                        "id": None,
                        "text": "+",
                        "css": "status-empty",
                        "has_data": False,
                        "date": gr_class.date,
                        "date_name": gr_class.name or "",
                        "gr_class_id": gr_class.id,
                    }
                )

        custumer_data.append(
            {
                "id": customer.id,
                "full_name": customer.full_name,
                "attendance_cells": attendance_cells,
            }
        )

    if is_assistant:
        employee_permissions = {
            "can_add_customers": (
                "Может добавлять клиентов" in user_permissions
            ),
            "can_add_classes": ("Может добавлять занятия" in user_permissions),
            "can_add_subscriptions": (
                "Может добавлять Абонементы" in user_permissions
            ),
            "can_mark_attendance": (
                "Может добавлять отметки посещаемости" in user_permissions
            ),
        }
    else:
        employee_permissions = {
            "can_add_customers": True,
            "can_add_classes": True,
            "can_add_subscriptions": True,
            "can_mark_attendance": True,
        }

    template = (
        "groups/detaile_date.html"
        if is_admin
        else "employe/groups/detail_date.html"
    )
    context = {
        "group": group,
        "calendar_days": calendar_days,
        "selected_date": selected_date,
        "prev_day": prev_day,
        "next_day": next_day,
        "group_classes": group_classes,
        "custumer_data": custumer_data,
        "employee_permissions": employee_permissions,
    }
    return render(request, template, context)


@login_required
def groups_custumer_create(request, pk):
    group = get_object_or_404(GroupsClass, id=pk)
    all_custumers = Custumer.objects.filter(company=request.user.company)
    selected_custumers = group.custumer_set.all()

    if request.method == "POST":
        custumer_ids = request.POST.getlist("custumer")
        custumers = Custumer.objects.filter(
            id__in=custumer_ids, company=request.user.company
        )

        with transaction.atomic():
            # Обработка удаленных клиентов
            removed_custumers = selected_custumers.exclude(id__in=custumer_ids)
            GroupClassessCustumer.objects.filter(
                custumer__in=removed_custumers, gr_class__groups_id=group
            ).update(is_none=True)
            group.custumer_set.remove(*removed_custumers)

            # Получаем все занятия группы один раз (вместо N запросов)
            group_classes = GroupClasses.objects.filter(groups_id=group)

            # Массовое добавление клиентов в группу (1 запрос вместо N)
            group.custumer_set.add(*custumers)

            # Подготовка всех записей посещаемости для массового создания
            attendance_records = []
            for custumer in custumers:
                for group_class in group_classes:
                    attendance_records.append(
                        GroupClassessCustumer(
                            gr_class=group_class,
                            custumer=custumer,
                            date=group_class.date,
                            is_none=False,
                            company=request.user.company,
                            owner=request.user,
                        )
                    )

            # Массовое создание записей (1 запрос вместо N × M)
            # ignore_conflicts пропустит дубликаты без ошибок
            GroupClassessCustumer.objects.bulk_create(
                attendance_records, ignore_conflicts=True
            )

            # Обновление существующих записей is_none=False (1 запрос)
            GroupClassessCustumer.objects.filter(
                custumer__in=custumers,
                gr_class__in=group_classes,
                is_none=True,
            ).update(is_none=False)

        return redirect("groups_custumer:groups_detail", pk=pk)

    context = {
        "group": group,
        "custumers": all_custumers,
        "selected_custumers": selected_custumers,
    }
    return render(request, "groups/add_custumer.html", context)


@login_required
def groups_classess_add(request, pk):
    user = request.user

    # Default template
    template = (
        "groups/add_classess.html"
        if user.groups.filter(name="admin").exists()
        else "groups/assistent/add_classess.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может добавлять занятие"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        group = get_object_or_404(GroupsClass, id=pk)
        employe = Employe.objects.filter(company=request.user.company)
        context = {}

        if request.method == "POST":
            name = request.POST.get("name")
            start_date_str = request.POST.get("start_date")
            strat = request.POST.get("strat")
            end = request.POST.get("end")
            employe = request.POST.get("employe")
            comment = request.POST.get("comment")

            if not start_date_str or not strat or not end or not employe:
                context["error"] = (
                    "Пожалуйста, заполните все обязательные поля."
                )
            else:
                empl = get_object_or_404(Employe, id=employe)
                start_date = datetime.strptime(
                    start_date_str, "%d.%m.%Y"
                ).date()
                group_class = GroupClasses(
                    name=name,
                    groups_id=group,
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
                custumers = Custumer.objects.filter(groups__id=group.id)
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
                return redirect("groups_custumer:groups_detail", pk=pk)

        context = {"group": group, "employe": employe}
        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def group_subscription_create(request, group_id, custumer_id):
    user = request.user

    # Default template
    template = (
        "groups/add_subscription.html"
        if user.groups.filter(name="admin").exists()
        else "groups/assistent/add_subscription.html"
    )

    if ensure_can_add_subscription(user):
        group = get_object_or_404(GroupsClass, id=group_id)
        custumer = get_object_or_404(Custumer, id=custumer_id)
        groups_qs = GroupsClass.objects.filter(id=group_id)
        cancel_url = reverse(
            "groups_custumer:groups_detail", kwargs={"pk": group_id}
        )

        extra_context = {"group": group}
        form_data = None

        if request.method == "POST":
            success, payload = process_subscription_submission(
                request=request,
                custumer=custumer,
                groups_qs=groups_qs,
                allow_group_selection=False,
            )
            if success:
                return redirect(
                    "groups_custumer:groups_detail",
                    pk=group_id,
                )

            extra_context["error"] = payload.get("error")
            form_data = payload.get("form_data")

        context = prepare_subscription_form_context(
            request=request,
            custumer=custumer,
            groups_qs=groups_qs,
            allow_group_selection=False,
            cancel_url=cancel_url,
            form_data=form_data,
            extra_context=extra_context,
        )

        return render(request, template, context)

    logout(request)
    return render(request, "page_404.html")


# Type Sports
@login_required
def type_sport(request):
    context = {}
    context["type_sport"] = TypeSportsCompany.objects.filter(
        company=request.user.company
    )
    return render(request, "groups/type_sport/index.html", context)


@login_required
def type_sport_create(request):
    context = {}

    if request.method == "POST":
        name = request.POST.get("name")

        if not name:
            context["error"] = "Поля обязательны для заполнения"
            return render(request, "groups/type_sport/create.html", context)

        sport = TypeSportsCompany(name=name, company=request.user.company)
        sport.save()
        return redirect("groups_custumer:type_sport")
    return render(request, "groups/type_sport/create.html", context)


@login_required
def type_sport_update(request, pk):
    context = {}
    context["type_sport"] = get_object_or_404(TypeSportsCompany, id=pk)
    if request.method == "POST":
        name = request.POST.get("name")

        if not name:
            context["error"] = "Поля обязательны для заполнения"
            return render(request, "groups/type_sport/update.html", context)

        context["type_sport"].name = name
        context["type_sport"].save()
        return redirect("groups_custumer:type_sport")

    return render(request, "groups/type_sport/update.html", context)


@login_required
def type_sport_delete(request, pk):
    tpe_sprot = get_object_or_404(TypeSportsCompany, id=pk)
    tpe_sprot.delete()
    return redirect("groups_custumer:type_sport")


@login_required
def get_customer_attendance_summary(request, group_id, customer_id):
    """
    Возвращает обновлённые данные по абонементам и неоплаченным
    занятиям клиента.
    """
    user = request.user
    is_admin, is_assistant, _ = _check_user_permissions(user)

    user_permissions = get_user_permissions(user)
    can_view_all_groups = "Может просматривать группы" in user_permissions
    can_view_own_groups = (
        "Может просматривать только свои группы" in user_permissions
    )
    can_view_classes = (
        "Может просматривать занятия только своих групп" in user_permissions
    )

    if not (
        is_admin
        or (
            is_assistant
            and (
                can_view_all_groups or can_view_own_groups or can_view_classes
            )
        )
    ):
        return JsonResponse(
            {"success": False, "error": "Доступ запрещён"}, status=403
        )

    group = get_object_or_404(GroupsClass, id=group_id)

    if is_assistant and (can_view_own_groups or can_view_classes):
        try:
            employe_instance = Employe.objects.get(user=user)
            is_member = group.employe_id.filter(
                id=employe_instance.id
            ).exists()
            if not is_member:
                return JsonResponse(
                    {"success": False, "error": "Доступ запрещён"},
                    status=403,
                )
        except Employe.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Доступ запрещён"}, status=403
            )

    customer = get_object_or_404(
        Custumer.objects.select_related("company", "owner").filter(
            groups=group
        ),
        id=customer_id,
    )

    mode = request.GET.get("mode", "month")

    if mode == "date":
        selected_date_str = request.GET.get("selected_date")
        if not selected_date_str:
            return JsonResponse(
                {"success": False, "error": "Не передана дата"}, status=400
            )
        try:
            selected_date = datetime.strptime(
                selected_date_str, "%Y-%m-%d"
            ).date()
        except ValueError:
            return JsonResponse(
                {"success": False, "error": "Некорректный формат даты"},
                status=400,
            )
        first_day = selected_date
        last_day = selected_date
    else:
        try:
            year = int(request.GET.get("year", date.today().year))
            month = int(request.GET.get("month", date.today().month))
        except ValueError:
            return JsonResponse(
                {"success": False, "error": "Некорректный месяц/год"},
                status=400,
            )
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

    subscriptions_qs = (
        CustumerSubscription.objects.filter(
            groups=group,
            custumer=customer,
            is_blok=False,
        )
        .select_related("custumer", "owner", "company")
        .prefetch_related("groups")
    )

    if mode == "date":
        subscriptions_qs = subscriptions_qs.filter(
            start_date__lte=last_day, end_date__gte=first_day
        )
    else:
        subscriptions_qs = subscriptions_qs.filter(
            start_date__lte=last_day, end_date__gte=first_day
        )

    subscriptions = list(subscriptions_qs.distinct())

    attendance_qs = (
        GroupClassessCustumer.objects.filter(
            custumer=customer,
            gr_class__groups_id=group,
            date__range=(first_day, last_day),
        )
        .select_related(
            "used_subscription",
            "gr_class",
            "gr_class__groups_id",
            "gr_class__employe",
        )
        .order_by("date")
    )

    attendance_by_subscription = {}
    for att in attendance_qs:
        if att.used_subscription_id:
            attendance_by_subscription.setdefault(
                att.used_subscription_id, []
            ).append(att)

    for subscription in subscriptions:
        subscription.filtered_attendance = attendance_by_subscription.get(
            subscription.id, []
        )

    unpaid_count = get_unpaid_count_for_customer_in_group(
        customer_id=customer.id,
        group_id=group.id,
    )

    customer_summary = SimpleNamespace(
        id=customer.id,
        full_name=customer.full_name,
        unpaid_count=unpaid_count,
        subscriptions=subscriptions,
    )

    if is_assistant:
        employee_permissions = {
            "can_add_customers": (
                "Может добавлять клиентов" in user_permissions
            ),
            "can_add_classes": ("Может добавлять занятия" in user_permissions),
            "can_add_subscriptions": (
                "Может добавлять Абонементы" in user_permissions
            ),
            "can_mark_attendance": (
                "Может добавлять отметки посещаемости" in user_permissions
            ),
        }
    else:
        employee_permissions = {
            "can_add_customers": True,
            "can_add_classes": True,
            "can_add_subscriptions": True,
            "can_mark_attendance": True,
        }

    desktop_html = render_to_string(
        "groups/includes/customer_subscription_links.html",
        {
            "customer": customer_summary,
            "group": group,
            "employee_permissions": employee_permissions,
            "variant": "desktop",
            "render_mode": "content",
        },
        request=request,
    )

    mobile_html = render_to_string(
        "groups/includes/customer_subscription_links.html",
        {
            "customer": customer_summary,
            "group": group,
            "employee_permissions": employee_permissions,
            "variant": "mobile",
            "render_mode": "content",
        },
        request=request,
    )

    modals_html = render_to_string(
        "groups/includes/customer_subscription_modals.html",
        {
            "customer": customer_summary,
            "group": group,
            "render_mode": "content",
        },
        request=request,
    )

    return JsonResponse(
        {
            "success": True,
            "desktop_html": desktop_html,
            "mobile_html": mobile_html,
            "modals_html": modals_html,
            "unpaid_count": unpaid_count,
        }
    )
