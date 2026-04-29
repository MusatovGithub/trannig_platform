from datetime import datetime

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from custumer.models import (
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from custumer.payment import services
from custumer.utils import get_user_permissions
from groups_custumer.models import GroupsClass


@login_required
def custumer_payment(request, pk):
    user = request.user
    custumer = get_object_or_404(Custumer, id=pk)
    group_id = request.GET.get("group")
    payment_status = request.GET.get("payment_status")
    attendance_status = request.GET.get("attendance_status")

    # Оптимизированная проверка роли пользователя
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    # **Rolga qarab template tanlash**
    if is_admin:
        template = "customer/payment/index.html"
    elif is_assistant:
        template = "customer/payment/assistant/index.html"
    else:
        logout(request)
        return render(request, "page_404.html")

    # Получаем все группы клиента
    all_groups = services.get_all_customer_groups(custumer.id)

    # Получаем группы с неоплаченными посещениями для пометки
    groups_with_unpaid_ids = set(
        services.get_customer_groups_with_unpaid_attendances(
            custumer.id
        ).values_list("id", flat=True)
    )

    # Получаем посещения
    if group_id:
        group_id = int(group_id)
        # При выборе группы показываем все посещения этой группы
        payment_queryset = services.get_all_attendances_by_group(
            custumer.id,
            group_id=group_id,
            payment_status=payment_status,
            attendance_status=attendance_status,
        )
    else:
        # Без выбранной группы показываем все посещения
        payment_queryset = services.get_all_attendances_by_group(
            custumer.id,
            group_id=None,
            payment_status=payment_status,
            attendance_status=attendance_status,
        )

    # Получаем все данные одним запросом
    payment_list = list(payment_queryset)

    # Определяем выбранную группу для контекста
    selected_group = None
    has_unpaid_in_selected_group = False
    if group_id:
        try:
            selected_group = GroupsClass.objects.get(id=group_id)
            # Проверяем наличие неоплаченных посещений в выбранной группе
            has_unpaid_in_selected_group = any(
                not item.is_block  # Прощенные имеют is_block=True
                and (
                    not item.used_subscription
                    or item.used_subscription.attendance_status == "unpaid"
                )
                and not (
                    item.used_subscription
                    and item.used_subscription.attendance_status == "none"
                )  # Исключаем бесплатные абонементы
                and item.attendance_status != "not_attended"
                # Исключаем прощенные посещения
                and not (
                    hasattr(item, "payment_record")
                    and item.payment_record
                    and item.payment_record.is_pay
                    and item.payment_record.subscription is None
                    and item.payment_record.summ == 0
                )
                for item in payment_list
                if item.owner
            )
        except GroupsClass.DoesNotExist:
            pass

    context = {
        "cutumer": custumer,
        "payment": payment_list,
        "groups": all_groups,
        "groups_with_unpaid_ids": groups_with_unpaid_ids,
        "selected_group": selected_group,
        "selected_group_id": group_id,
        "has_unpaid_in_selected_group": has_unpaid_in_selected_group,
    }

    return render(request, template, context)


@login_required
@transaction.atomic
def custumer_payment_create(request, custumer_id, group_id):
    user = request.user

    # Проверяем валидность group_id
    if not group_id or group_id == 0:
        return render(request, "page_404.html", status=404)

    # Default template
    template = (
        "customer/payment/create.html"
        if user.groups.filter(name="admin").exists()
        else "customer/payment/assistant/create.html"
    )

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_add_payments"]
    ):
        context = {}

        custumer = get_object_or_404(Custumer, id=custumer_id)
        group = get_object_or_404(GroupsClass, id=group_id)

        # Получаем неоплаченные занятия через сервис
        payment_queryset = services.get_unpaid_attendances_by_group(
            custumer.id, group_id
        )
        context["payment"] = list(payment_queryset)

        # Получаем кассиров через сервис
        context["cashier"] = list(
            services.get_cashiers_for_company(request.user.company)
        )

        # Получаем абонементы через сервис
        context["subscription"] = list(
            services.get_available_subscriptions_for_group(
                custumer.id, group_id
            )
        )

        if request.method == "POST":
            duration_type = request.POST.get("duration_type")

            if duration_type == "payment":  # "Оплатить"
                payment_ids = request.POST.getlist("payment")
                summ = request.POST.get("summ")
                cashier_id = request.POST.get("cashier")
                summ_date = request.POST.get("summ_date")

                if (
                    not summ
                    or not cashier_id
                    or not summ_date
                    or not payment_ids
                ):
                    context["error"] = "Заполните все поля!"
                    return render(request, template, context)

                try:
                    formatted_date = datetime.strptime(
                        summ_date, "%d.%m.%Y"
                    ).date()
                except ValueError:
                    context["error"] = (
                        "Неверный формат даты! Введите в формате DD.MM.YYYY."
                    )
                    return render(request, template, context)

                try:
                    # Используем сервис для обработки оплаты
                    services.process_payment_for_attendances(
                        customer=custumer,
                        group=group,
                        attendance_ids=[int(pid) for pid in payment_ids],
                        summ=int(summ),
                        cashier_id=int(cashier_id),
                        summ_date=formatted_date,
                        company=request.user.company,
                        owner=request.user,
                    )
                except Exception as e:
                    context["error"] = f"Ошибка при обработке оплаты: {str(e)}"
                    return render(request, template, context)

                return redirect("groups_custumer:groups_detail", pk=group_id)

            elif duration_type == "subscription":  # "Списать с абонемента"
                payment_ids = request.POST.getlist("payment2")
                subscription_id = request.POST.get("subscriptionSelect")

                if not payment_ids or not subscription_id:
                    context["error"] = "Выберите посещения и абонемент!"
                    return render(request, template, context)

                try:
                    # Используем сервис для обработки списания с абонемента
                    services.process_subscription_payment(
                        customer=custumer,
                        group=group,
                        attendance_ids=[int(pid) for pid in payment_ids],
                        subscription_id=int(subscription_id),
                    )
                except ValueError as e:
                    context["error"] = str(e)
                    return render(request, template, context)
                except Exception as e:
                    context["error"] = (
                        f"Ошибка при обработке списания: {str(e)}"
                    )
                    return render(request, template, context)

                return redirect("groups_custumer:groups_detail", pk=group_id)

            elif duration_type == "free":  # "Простить"
                payment_ids = request.POST.getlist("payment3")

                if not payment_ids:
                    context["error"] = "Выберите посещения для списания!"
                    return render(request, template, context)

                try:
                    # Используем сервис для обработки прощения
                    services.forgive_attendances(
                        customer=custumer,
                        group=group,
                        attendance_ids=[int(pid) for pid in payment_ids],
                        company=request.user.company,
                        owner=request.user,
                    )
                except Exception as e:
                    context["error"] = (
                        f"Ошибка при обработке прощения: {str(e)}"
                    )
                    return render(request, template, context)

                return redirect("groups_custumer:groups_detail", pk=group_id)

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def get_attendances_by_group_ajax(request, customer_id, group_id):
    """
    AJAX endpoint для загрузки посещений по группе.

    Args:
        request: HTTP запрос
        customer_id: ID клиента
        group_id: ID группы (может быть 0 или None)

    Returns:
        JSON ответ с данными посещений
    """
    user = request.user

    # Проверяем разрешения
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    if not (is_admin or is_assistant):
        return JsonResponse({"error": "Доступ запрещен"}, status=403)

    try:
        customer = Custumer.objects.get(id=customer_id)
    except Custumer.DoesNotExist:
        return JsonResponse({"error": "Клиент не найден"}, status=404)

    # Проверяем валидность group_id
    if not group_id or group_id == 0:
        return JsonResponse(
            {
                "success": True,
                "attendances": [],
                "has_unpaid": False,
                "group_id": None,
                "group_name": "",
                "customer_id": customer.id,
                "message": "Выберите группу для просмотра посещений",
            }
        )

    try:
        group = GroupsClass.objects.get(id=group_id)
    except GroupsClass.DoesNotExist:
        return JsonResponse({"error": "Группа не найдена"}, status=404)

    # Получаем параметры фильтрации из запроса
    payment_status = request.GET.get("payment_status")
    attendance_status = request.GET.get("attendance_status")

    # Получаем все посещения группы через сервис
    attendances = services.get_all_attendances_by_group(
        customer.id,
        group_id=group.id,
        payment_status=payment_status,
        attendance_status=attendance_status,
    )

    # Формируем данные для ответа
    attendances_data = []
    for attendance in attendances:
        attendances_data.append(
            {
                "id": attendance.id,
                "date": attendance.date.strftime("%d.%m.%Y")
                if attendance.date
                else "",
                "class_time": str(attendance.class_time)
                if attendance.class_time
                else "",
                "attendance_status": attendance.attendance_status,
                "group_name": str(attendance.gr_class.groups_id)
                if attendance.gr_class
                else "",
                "is_block": attendance.is_block,
                "has_subscription": (attendance.used_subscription is not None),
                "subscription_status": (
                    attendance.used_subscription.attendance_status
                    if attendance.used_subscription
                    else None
                ),
                "payment_status_display": attendance.payment_status_display,
                "is_payment_blocked": attendance.is_payment_blocked,
                "owner": str(attendance.owner) if attendance.owner else "",
                "update_at": (
                    attendance.update_at.strftime("%d.%m.%Y %H:%M")
                    if attendance.update_at
                    else ""
                ),
            }
        )

    # Проверяем, есть ли неоплаченные посещения
    # Исключаем прощенные посещения
    has_unpaid = any(
        not att["is_block"]  # Прощенные имеют is_block=True
        and (
            not att["has_subscription"]
            or att["subscription_status"] == "unpaid"
        )
        and att["attendance_status"] != "not_attended"
        # Исключаем прощенные посещения (payment_status_display == "Прощено")
        and att.get("payment_status_display") != "Прощено"
        for att in attendances_data
    )

    return JsonResponse(
        {
            "success": True,
            "attendances": attendances_data,
            "has_unpaid": has_unpaid,
            "group_id": group.id,
            "group_name": str(group),
            "customer_id": customer.id,
        }
    )


@login_required
def custumer_payment_history(request, pk):
    context = {}
    user = request.user
    context["cutumer"] = get_object_or_404(Custumer, id=pk)

    # Оптимизированный запрос для истории платежей
    # Включаем как обычные оплаты, так и прощенные посещения
    context["payment"] = (
        CustumerSubscriptonPayment.objects.filter(
            custumer=context["cutumer"],
            summ_date__isnull=False,
            is_pay=True,  # Только оплаченные (включая прощенные)
        )
        .filter(
            # Обычные оплаты: наличными (summ > 0, cashier не null)
            # или абонементом (subscription не null)
            Q(summ__gt=0)
            | Q(subscription__isnull=False)
            # ИЛИ прощенные посещения (summ=0, cashier=None, subscription=None)
            | Q(summ=0, cashier__isnull=True, subscription__isnull=True)
        )
        .select_related(
            "custumer",
            "custumer__user",  # Пользователь клиента
            "groups",  # Группа
            "groups__owner_id",  # Владелец группы
            "subscription",  # Абонемент
            "subscription__owner",  # Владелец абонемента
            "cashier",  # Кассир
            "owner",  # Владелец записи платежа
        )
        .prefetch_related(
            "subscription__payments",  # Связанные платежи абонементов
        )
    )

    # Вычисляем общий остаток долга по всем неоплаченным абонементам
    # Используем prefetch_related для избежания N+1 запросов
    unpaid_subscriptions = (
        CustumerSubscription.objects.filter(
            custumer=context["cutumer"],
            attendance_status="unpaid",
            is_free=False,
        )
        .select_related(
            "custumer",
            "custumer__user",  # Пользователь клиента
        )
        .prefetch_related(
            "payments",  # Связанные платежи для расчета remaining_amount
        )
    )

    # Вычисляем общий долг, используя prefetch_related
    total_debt = sum(
        subscription.remaining_amount for subscription in unpaid_subscriptions
    )
    context["total_debt"] = total_debt

    # Оптимизированная проверка роли пользователя
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    if is_admin:
        template = "customer/payment/history.html"
    elif is_assistant:
        template = "customer/payment/assistant/history.html"
    else:
        logout(request)
        return render(request, "page_404.html")

    return render(request, template, context)


@login_required
def custumer_payment_delete(request, custumer_id, payment_id):
    user = request.user

    # Оптимизированная проверка роли пользователя
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if is_admin or user_permissions["can_delete_payments"]:
        custumer = get_object_or_404(Custumer, id=custumer_id)
        payment = get_object_or_404(CustumerSubscriptonPayment, id=payment_id)
        payment.delete()
        return redirect("customer:custumer_payment_history", pk=custumer.id)
    logout(request)
    return render(request, "page_404.html")
