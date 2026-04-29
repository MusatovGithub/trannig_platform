import logging
from datetime import datetime

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from base.cache_utils import (
    get_cached_cashiers,
    get_cached_company_groups,
    get_cached_subscription_templates,
)
from custumer.models import (
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from custumer.subscription.services import (
    ensure_can_add_subscription,
    prepare_subscription_form_context,
    process_subscription_submission,
)
from custumer.utils import get_user_permissions
from groups_custumer.models import GroupClassessCustumer, GroupsClass

logger = logging.getLogger(__name__)


@login_required
def custumer_subscriptions(request, pk):
    user = request.user
    custumer = get_object_or_404(Custumer, id=pk)

    # Оптимизированный запрос для абонементов
    subscription = (
        CustumerSubscription.objects.filter(custumer=custumer)
        .select_related(
            "custumer",
            "custumer__user",  # Пользователь клиента
            "owner",  # Владелец абонемента
        )
        .prefetch_related(
            "payments",  # Связанные платежи
            "groups",  # Группы абонемента
            "payments__cashier",  # Кассиры для платежей
            "payments__owner",  # Владельцы платежей
        )
    )

    # Оптимизированный запрос для посещений
    # (используется только в админском шаблоне)
    attendance = (
        GroupClassessCustumer.objects.filter(
            custumer=custumer, used_subscription_id__in=subscription
        )
        .exclude(attendance_status="none")
        .select_related(
            "custumer",
            "custumer__user",  # Пользователь клиента
            "gr_class",
            "gr_class__groups_id",
            "gr_class__employe",
            "gr_class__employe__user",  # Пользователь тренера
            "gr_class__company",
            "gr_class__owner",
            "used_subscription",
            "used_subscription__owner",  # Владелец абонемента
        )
    )

    # Оптимизированная проверка роли пользователя
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    if is_admin:
        template = "customer/subscriptions/index.html"
    elif is_assistant:
        template = "customer/subscriptions/assistant/index.html"
        # Получаем разрешения пользователя одним оптимизированным запросом
        user_permissions = get_user_permissions(user)
    else:
        logout(request)
        return render(request, "page_404.html")

    context = {
        "custumer": custumer,
        "subscription": subscription,
        "attendance": attendance,
    }

    if is_assistant:
        context["user_permissions"] = user_permissions

    return render(request, template, context)


@login_required
def custumer_subscriptions_add(request, pk):
    user = request.user

    # Default template
    template = (
        "customer/subscriptions/create.html"
        if user.groups.filter(name="admin").exists()
        else "customer/subscriptions/assistant/create.html"
    )

    if ensure_can_add_subscription(user):
        custumer = get_object_or_404(Custumer, id=pk)
        groups_qs = GroupsClass.objects.filter(company=request.user.company)
        cancel_url = reverse(
            "customer:custumer_subscriptions", kwargs={"pk": custumer.id}
        )

        extra_context = {}
        form_data = None

        if request.method == "POST":
            success, payload = process_subscription_submission(
                request=request,
                custumer=custumer,
                groups_qs=groups_qs,
                allow_group_selection=True,
            )
            if success:
                return redirect(
                    "customer:custumer_subscriptions",
                    pk=custumer.id,
                )

            extra_context["error"] = payload.get("error")
            form_data = payload.get("form_data")

        context = prepare_subscription_form_context(
            request=request,
            custumer=custumer,
            groups_qs=groups_qs,
            allow_group_selection=True,
            cancel_url=cancel_url,
            form_data=form_data,
            extra_context=extra_context,
        )

        return render(request, template, context)

    logout(request)
    return render(request, "page_404.html")


@login_required
@transaction.atomic
def custumer_subscriptions_update(request, custumer_id, sub_id):
    """
    Обновление абонемента клиента с защитой от race conditions
    и асинхронной обработкой тяжелых операций.
    """
    from custumer.subscription.services import (
        update_subscription_core,
        update_subscription_groups,
        update_subscription_payments,
        validate_subscription_dates,
        validate_subscription_update,
    )
    from custumer.tasks import (
        auto_bind_attendances_to_subscription,
        recalculate_subscription_attendances_on_groups_change,
        recalculate_subscription_payment_status,
    )

    user = request.user

    # Логируем начало операции обновления
    logger.info(
        f"Updating subscription {sub_id} for customer {custumer_id} "
        f"by user {user.id} ({user.username})"
    )

    # Default template
    template = (
        "customer/subscriptions/update.html"
        if user.groups.filter(name="admin").exists()
        else "customer/subscriptions/assistant/update.html"
    )

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if not (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_edit_subscriptions"]
    ):
        logout(request)
        return render(request, "page_404.html")

    # Получаем основные объекты
    custumer = get_object_or_404(Custumer, id=custumer_id)
    subscription = get_object_or_404(CustumerSubscription, id=sub_id)
    payment = CustumerSubscriptonPayment.objects.filter(
        subscription=subscription
    ).first()

    # Контекст для формы
    company_id = request.user.company.id
    context = {
        "temp": get_cached_subscription_templates(company_id),
        "payment": payment,
        "custumer": custumer,
        "subscription": subscription,
        "group": get_cached_company_groups(company_id),
        "cashier": get_cached_cashiers(company_id),
    }

    if request.method == "GET":
        context["form_data"] = {
            "number": subscription.number_classes,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "unlimited": subscription.unlimited,
            "price": subscription.total_cost,
        }
        return render(request, template, context)

    # POST request - обработка обновления
    group_ids = request.POST.getlist("group")
    number = request.POST.get("number")
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")
    unlimited = "unlimited" in request.POST
    is_free = "is_free" in request.POST
    price = request.POST.get("price")
    summ = request.POST.get("summ")
    cashier_id = request.POST.get("cashier")
    date_summ = request.POST.get("date_summ")

    # 1. Валидация данных
    is_valid, error_msg = validate_subscription_update(
        group_ids=group_ids,
        start_date=start_date,
        end_date=end_date,
        number=number,
        unlimited=unlimited,
        subscription_id=sub_id,
    )
    if not is_valid:
        context["error"] = error_msg
        context["form_data"] = {
            "number": number,
            "start_date": start_date,
            "end_date": end_date,
            "unlimited": unlimited,
            "is_free": is_free,
            "price": price,
            "summ": summ,
            "cashier": cashier_id,
            "date_summ": date_summ,
            "group_ids": group_ids,
        }
        return render(request, template, context)

    # Преобразуем даты
    start_date_obj = datetime.strptime(start_date, "%d.%m.%Y").date()
    end_date_obj = datetime.strptime(end_date, "%d.%m.%Y").date()

    # 2. Проверка дат
    date_validation = validate_subscription_dates(
        subscription_id=sub_id,
        new_start_date=start_date_obj,
        new_end_date=end_date_obj,
    )
    if not date_validation["valid"]:
        context["error"] = date_validation["error"]
        context["form_data"] = {
            "number": number,
            "start_date": start_date,
            "end_date": end_date,
            "unlimited": unlimited,
            "is_free": is_free,
            "price": price,
            "summ": summ,
            "cashier": cashier_id,
            "date_summ": date_summ,
            "group_ids": group_ids,
        }
        return render(request, template, context)

    # 3. Проверка изменений в группах
    group_change_result = update_subscription_groups(
        subscription_id=sub_id,
        new_group_ids=[int(gid) for gid in group_ids],
    )

    # 4. Определяем статус оплаты
    if is_free:
        attendance_status = "none"
    else:
        if summ and price and int(summ) == int(price):
            attendance_status = "paid"
        else:
            attendance_status = "unpaid"

    # 5. Обновляем основные данные абонемента
    subscription, dates_changed = update_subscription_core(
        subscription_id=sub_id,
        data={
            "number": number if number else None,
            "start_date": start_date_obj,
            "end_date": end_date_obj,
            "unlimited": unlimited,
            "is_free": is_free,
            "price": price if price else 0,
            "attendance_status": attendance_status,
            "group_ids": [int(gid) for gid in group_ids],
        },
    )

    # 6. Обновляем платежи
    update_subscription_payments(
        subscription_id=sub_id,
        customer_id=custumer_id,
        group_ids=[int(gid) for gid in group_ids],
        payment_data={
            "summ": summ,
            "cashier_id": cashier_id,
            "date_summ": date_summ,
        },
    )

    # 7. Запускаем асинхронные задачи после коммита транзакции
    if group_change_result["has_changes"]:
        task = recalculate_subscription_attendances_on_groups_change
        transaction.on_commit(
            lambda: task.delay(
                subscription_id=sub_id,
                removed_group_ids=group_change_result["removed_groups"],
            )
        )

    # Автоматическая привязка посещений при изменении дат
    if dates_changed:
        transaction.on_commit(
            lambda: auto_bind_attendances_to_subscription.delay(
                subscription_id=sub_id
            )
        )

    # Пересчитываем статус оплаты асинхронно
    transaction.on_commit(
        lambda: recalculate_subscription_payment_status.delay(
            subscription_id=sub_id
        )
    )

    # Логируем успешное завершение
    logger.info(
        f"Successfully updated subscription {sub_id}. "
        f"Dates changed: {dates_changed}, "
        f"Groups changed: {group_change_result['has_changes']}, "
        f"User: {user.id}"
    )

    return redirect("customer:custumer_subscriptions", pk=custumer.id)


@login_required
@transaction.atomic
def custumer_subscriptions_detele(request, custumer_id, sub_id):
    user = request.user

    # Логируем начало операции удаления
    logger.warning(
        f"Attempting to delete subscription {sub_id} for "
        f"customer {custumer_id} by user {user.id} ({user.username})"
    )

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    # Удаляем платежи для конкретных дат
    if (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_delete_subscriptions"]
    ):
        subscription = get_object_or_404(CustumerSubscription, id=sub_id)

        # Получаем посещения, связанные с абонементом
        # ВАЖНО: НЕ используем select_related, так как связи будут нарушены
        # при удалении. Вместо этого получаем только нужные данные.
        affected_attendances_data = list(
            GroupClassessCustumer.objects.filter(
                used_subscription=subscription,
                attendance_status__in=[
                    "attended_2",
                    "attended_3",
                    "attended_4",
                    "attended_5",
                    "attended_10",
                ],
            ).values(
                "id",
                "custumer_id",
                "gr_class__groups_id",
                "date",
            )
        )

        # Создаем записи неоплаченных посещений для непустых абонементов
        # НО только если абонемент был не бесплатный
        if (
            subscription.attendance_status in ["unpaid", "paid"]
            and affected_attendances_data
        ):
            payments_to_create = []
            for attendance_data in affected_attendances_data:
                payments_to_create.append(
                    CustumerSubscriptonPayment(
                        custumer_id=attendance_data["custumer_id"],
                        groups_id=attendance_data["gr_class__groups_id"],
                        subscription=None,
                        summ=0,
                        sub_date=attendance_data["date"],
                        is_pay=False,
                        is_blok=False,
                        company=subscription.company,
                        owner=subscription.owner,
                    )
                )
            if payments_to_create:
                CustumerSubscriptonPayment.objects.bulk_create(
                    payments_to_create, ignore_conflicts=True
                )

        # Сигнал pre_delete автоматически сбросит is_block для всех посещений

        custumer = get_object_or_404(Custumer, id=custumer_id)

        # Логируем перед удалением
        logger.info(
            f"Deleting subscription {sub_id}. "
            f"Affected attendances: {len(affected_attendances_data)}, "
            f"User: {user.id}"
        )

        subscription.delete()

        logger.info(f"Successfully deleted subscription {sub_id}")

        return redirect("customer:custumer_subscriptions", pk=custumer.id)
    logout(request)
    return render(request, "page_404.html")


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def close_subscription(request, sub_id):
    """Закрытие абонемента с проверкой оплаченности."""
    user = request.user

    # Проверяем права пользователя
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    if not (is_admin or is_assistant):
        return JsonResponse(
            {"success": False, "error": "Недостаточно прав"}, status=403
        )

    try:
        subscription = get_object_or_404(CustumerSubscription, id=sub_id)
        # Проверяем, что абонемент принадлежит компании пользователя
        if subscription.company != user.company:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Абонемент не принадлежит компании пользователя",
                },
                status=404,
            )

        # Проверяем, что абонемент не неоплачен
        if subscription.attendance_status == "unpaid":
            return JsonResponse(
                {
                    "success": False,
                    "error": "Нельзя закрыть неоплаченный абонемент",
                },
                status=400,
            )

        # Проверяем, что абонемент ещё не закрыт
        if subscription.is_blok:
            return JsonResponse(
                {"success": False, "error": "Абонемент уже закрыт"}, status=400
            )

        # Закрываем абонемент
        subscription.is_blok = True
        subscription.closing_date = timezone.now().date()
        subscription.save()

        return JsonResponse(
            {"success": True, "message": "Абонемент успешно закрыт"}
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "error": f"Ошибка при закрытии абонемента: {str(e)}",
            },
            status=500,
        )


@login_required
@require_http_methods(["POST"])
def open_subscription(request, sub_id):
    """Открытие абонемента."""
    user = request.user

    # Проверяем права пользователя
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    if not (is_admin or is_assistant):
        return JsonResponse(
            {"success": False, "error": "Недостаточно прав"}, status=403
        )
    try:
        subscription = get_object_or_404(CustumerSubscription, id=sub_id)
        custumer_id = subscription.custumer.id
        subscription.is_blok = False
        subscription.closing_date = None
        subscription.save()
        # Перенаправляем обратно на страницу абонементов клиента
        return redirect("customer:custumer_subscriptions", pk=custumer_id)
    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "error": f"Ошибка при открытии абонемента: {str(e)}",
            },
            status=500,
        )


@login_required
def subscription_detail(request, sub_id):
    """
    Детальная страница абонемента.

    C посещениями, платежами и возможностью закрыть/создать новый.
    """
    user = request.user

    # Получаем абонемент с оптимизированными запросами
    subscription = get_object_or_404(
        CustumerSubscription.objects.select_related(
            "custumer", "custumer__user", "owner", "company"
        ).prefetch_related(
            "groups",
            "payments",
            "payments__cashier",
            "payments__owner",
            "used_attendances",
            "used_attendances__gr_class",
            "used_attendances__gr_class__groups_id",
            "used_attendances__gr_class__employe",
            "used_attendances__gr_class__employe__user",
        ),
        id=sub_id,
        custumer__company=user.company,
    )

    # Получаем посещения по этому абонементу
    attendances = (
        GroupClassessCustumer.objects.filter(
            used_subscription=subscription, custumer=subscription.custumer
        )
        .exclude(attendance_status="none")
        .select_related(
            "gr_class",
            "gr_class__groups_id",
            "gr_class__employe",
            "gr_class__employe__user",
            "gr_class__company",
        )
        .order_by("-gr_class__date", "-gr_class__strat")
    )

    # Получаем платежи по абонементу
    payments = subscription.payments.select_related(
        "cashier", "owner", "custumer", "groups"
    ).order_by("-summ_date", "-create_at")

    # Получаем доступные шаблоны абонементов для создания нового
    company_id = user.company.id
    subscription_templates = get_cached_subscription_templates(company_id)

    # Получаем доступные кассы
    cashiers = get_cached_cashiers(company_id)

    # Получаем группы клиента для нового абонемента
    customer_groups = subscription.custumer.groups.all()

    context = {
        "subscription": subscription,
        "attendances": attendances,
        "payments": payments,
        "subscription_templates": subscription_templates,
        "cashiers": cashiers,
        "customer_groups": customer_groups,
        "custumer": subscription.custumer,
    }

    return render(request, "customer/subscriptions/detail.html", context)
