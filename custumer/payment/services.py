"""
Сервисный слой для работы с оплатой посещений.
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q, QuerySet, Value
from django.db.models.functions import Coalesce

from base.cache_utils import CACHE_TIMEOUTS, get_cached_cashiers
from custumer.models import (
    Cashier,
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from groups_custumer.models import GroupClassessCustumer, GroupsClass

# Статусы посещений, которые считаются посещенными
ATTENDED_STATUSES = [
    "attended_2",
    "attended_3",
    "attended_4",
    "attended_5",
    "attended_10",
]


def get_customer_groups_with_unpaid_attendances(
    customer_id: int,
) -> QuerySet[GroupsClass]:
    """
    Получить группы клиента, в которых есть неоплаченные посещения.

    Args:
        customer_id: ID клиента

    Returns:
        QuerySet групп с неоплаченными посещениями
    """
    # Получаем группы, в которых есть неоплаченные посещения
    # Исключаем прощенные посещения (is_block=True с payment_record summ=0)
    # Используем подзапрос для более надежной проверки прощенных
    forgiven_attendance_ids = CustumerSubscriptonPayment.objects.filter(
        attendance_record__custumer_id=customer_id,
        attendance_record__attendance_status__in=ATTENDED_STATUSES,
        subscription__isnull=True,
        is_pay=True,
        summ=0,
    ).values_list("attendance_record_id", flat=True)

    groups_with_unpaid = (
        GroupClassessCustumer.objects.filter(
            custumer_id=customer_id,
            attendance_status__in=ATTENDED_STATUSES,
            is_block=False,  # Прощенные имеют is_block=True
        )
        .filter(
            Q(used_subscription__isnull=True)  # Без абонемента
            | Q(used_subscription__attendance_status="unpaid")  # Неоплаченный
        )
        .exclude(
            used_subscription__attendance_status="none"  # Исключаем бесплатные абонементы
        )
        # Исключаем прощенные посещения (через подзапрос)
        .exclude(id__in=forgiven_attendance_ids)
        .values_list("gr_class__groups_id", flat=True)
        .distinct()
    )

    # Возвращаем группы с оптимизацией
    return GroupsClass.objects.filter(
        id__in=groups_with_unpaid
    ).select_related("type_sport", "owner_id")


def get_all_customer_groups(customer_id: int) -> QuerySet[GroupsClass]:
    """
    Получить все группы клиента (из посещений и из связей).

    Args:
        customer_id: ID клиента

    Returns:
        QuerySet всех групп клиента
    """
    # Получаем группы из посещений
    groups_from_attendances = (
        GroupClassessCustumer.objects.filter(custumer_id=customer_id)
        .exclude(gr_class__groups_id__isnull=True)
        .values_list("gr_class__groups_id", flat=True)
        .distinct()
    )

    # Получаем группы из прямой связи ManyToMany
    try:
        customer = Custumer.objects.get(id=customer_id)
        groups_from_relation = customer.groups.values_list("id", flat=True)
    except Custumer.DoesNotExist:
        groups_from_relation = []

    # Объединяем все группы
    all_group_ids = set(groups_from_attendances) | set(groups_from_relation)

    # Если нет групп, возвращаем пустой QuerySet
    if not all_group_ids:
        return GroupsClass.objects.none()

    # Возвращаем группы с оптимизацией
    return GroupsClass.objects.filter(id__in=all_group_ids).select_related(
        "type_sport", "owner_id"
    )


def get_unpaid_attendances_by_group(
    customer_id: int,
    group_id: int,
    payment_status: Optional[str] = None,
    attendance_status: Optional[str] = None,
) -> QuerySet[GroupClassessCustumer]:
    """
    Получить неоплаченные посещения клиента по группе.

    Args:
        customer_id: ID клиента
        group_id: ID группы
        payment_status: Фильтр по статусу оплаты (free, unpaid, paid)
        attendance_status: Фильтр по статусу посещения

    Returns:
        QuerySet неоплаченных посещений
    """
    # Prefetch для payment_record (обратная связь OneToOneField)
    payment_prefetch = Prefetch(
        "payment_record",
        queryset=CustumerSubscriptonPayment.objects.select_related(
            "cashier", "subscription"
        ),
    )

    # Используем подзапрос для исключения прощенных посещений
    forgiven_attendance_ids = CustumerSubscriptonPayment.objects.filter(
        attendance_record__custumer_id=customer_id,
        attendance_record__gr_class__groups_id=group_id,
        attendance_record__attendance_status__in=ATTENDED_STATUSES,
        subscription__isnull=True,
        is_pay=True,
        summ=0,
    ).values_list("attendance_record_id", flat=True)

    queryset = (
        GroupClassessCustumer.objects.filter(
            custumer_id=customer_id,
            gr_class__groups_id=group_id,
            attendance_status__in=ATTENDED_STATUSES,
            is_block=False,  # Прощенные имеют is_block=True
        )
        .filter(
            Q(used_subscription__isnull=True)  # Без абонемента
            | Q(used_subscription__attendance_status="unpaid")  # Неоплаченный
        )
        .exclude(
            used_subscription__attendance_status="none"  # Исключаем бесплатные абонементы
        )
        # Исключаем прощенные посещения (через подзапрос)
        .exclude(id__in=forgiven_attendance_ids)
        .select_related(
            "gr_class__groups_id",
            "gr_class__groups_id__owner_id",
            "gr_class__employe",
            "gr_class__employe__user",
            "used_subscription",
            "used_subscription__owner",
            "custumer",
            "custumer__user",
            "owner",
        )
        .prefetch_related(payment_prefetch)
        .order_by("-date", "-class_time")
    )

    # Применяем дополнительные фильтры
    if payment_status:
        if payment_status == "free":
            queryset = queryset.filter(
                used_subscription__isnull=False,
                used_subscription__attendance_status="none",
            )
        elif payment_status == "unpaid":
            queryset = queryset.filter(used_subscription__isnull=True).filter(
                attendance_status__in=ATTENDED_STATUSES
            )
        elif payment_status == "paid":
            queryset = queryset.filter(
                used_subscription__isnull=False,
                used_subscription__attendance_status="paid",
            )

    if attendance_status:
        if attendance_status == "attended":
            queryset = queryset.filter(attendance_status__in=ATTENDED_STATUSES)
        else:
            queryset = queryset.filter(
                attendance_status__iexact=attendance_status
            )

    return queryset


def get_all_attendances_by_group(
    customer_id: int,
    group_id: Optional[int] = None,
    payment_status: Optional[str] = None,
    attendance_status: Optional[str] = None,
) -> QuerySet[GroupClassessCustumer]:
    """
    Получить все посещения клиента (с фильтрацией по группе, если указана).

    Args:
        customer_id: ID клиента
        group_id: ID группы (опционально)
        payment_status: Фильтр по статусу оплаты
        attendance_status: Фильтр по статусу посещения

    Returns:
        QuerySet посещений
    """
    queryset = (
        GroupClassessCustumer.objects.filter(
            custumer_id=customer_id,
            attendance_status__in=[
                "not_attended",
                "attended_2",
                "attended_3",
                "attended_4",
                "attended_5",
                "attended_10",
            ],
        )
        .select_related(
            "gr_class__groups_id",
            "gr_class__groups_id__owner_id",
            "gr_class__employe",
            "gr_class__employe__user",
            "used_subscription",
            "used_subscription__owner",
            "custumer",
            "custumer__user",
            "owner",
        )
        .prefetch_related(
            Prefetch(
                "payment_record",
                queryset=CustumerSubscriptonPayment.objects.select_related(
                    "cashier", "subscription"
                ),
            ),
        )
    )

    if group_id:
        queryset = queryset.filter(gr_class__groups_id=group_id)

    if payment_status:
        if payment_status == "free":
            queryset = queryset.filter(
                used_subscription__isnull=False,
                used_subscription__attendance_status="none",
            )
        elif payment_status == "unpaid":
            # Используем подзапрос для исключения
            # оплаченных и прощенных посещений
            paid_attendance_ids = (
                CustumerSubscriptonPayment.objects.filter(
                    attendance_record__custumer_id=customer_id,
                    subscription__isnull=True,
                    is_pay=True,
                )
                .exclude(summ=0)
                .values_list("attendance_record_id", flat=True)
            )

            forgiven_attendance_ids = (
                CustumerSubscriptonPayment.objects.filter(
                    attendance_record__custumer_id=customer_id,
                    subscription__isnull=True,
                    is_pay=True,
                    summ=0,
                ).values_list("attendance_record_id", flat=True)
            )

            queryset = queryset.filter(
                used_subscription__isnull=True,
                is_block=False,  # Прощенные имеют is_block=True
                attendance_status__in=ATTENDED_STATUSES,
            ).exclude(
                # Исключаем оплаченные наличными и прощенные посещения
                id__in=list(paid_attendance_ids)
                + list(forgiven_attendance_ids)
            )
        elif payment_status == "paid":
            queryset = queryset.filter(
                Q(used_subscription__attendance_status="paid")
                | Q(is_block=True),
            )

    if attendance_status:
        if attendance_status == "attended":
            queryset = queryset.filter(attendance_status__in=ATTENDED_STATUSES)
        else:
            queryset = queryset.filter(
                attendance_status__iexact=attendance_status
            )

    return queryset.order_by("-date", "-class_time")


@transaction.atomic
def process_payment_for_attendances(
    customer: Custumer,
    group: GroupsClass,
    attendance_ids: List[int],
    summ: int,
    cashier_id: int,
    summ_date: date,
    company,
    owner,
) -> Tuple[List[CustumerSubscriptonPayment], List[CustumerSubscriptonPayment]]:
    """
    Обработка оплаты посещений наличными.

    Args:
        customer: Клиент
        group: Группа
        attendance_ids: Список ID посещений для оплаты
        summ: Сумма платежа
        cashier_id: ID кассира
        summ_date: Дата платежа
        company: Компания
        owner: Владелец (пользователь)

    Returns:
        Кортеж (созданные платежи, обновленные платежи)
    """
    # Получаем посещения для оплаты
    attendances = GroupClassessCustumer.objects.filter(id__in=attendance_ids)

    for attendance in attendances:
        if attendance.used_subscription:
            raise ValueError(
                f"Посещение {attendance.id} уже оплачено абонементом!"
            )

    # Обновляем статус блокировки
    attendances.update(is_block=True)

    cashier = Cashier.objects.get(id=cashier_id)

    # ✅ ПОЛУЧАЕМ СУЩЕСТВУЮЩИЕ ЗАПИСИ ПО ID ПОСЕЩЕНИЙ
    existing_payments = {
        payment.attendance_record_id: payment
        for payment in CustumerSubscriptonPayment.objects.filter(
            attendance_record_id__in=attendance_ids,
            subscription=None,
        )
    }

    payments_to_create = []
    payments_to_update = []

    # Создаем или обновляем записи об оплате
    payments_to_create = []
    payments_to_update = []

    for attendance in attendances:
        if attendance.id in existing_payments:
            # Обновляем существующую запись
            existing_payment = existing_payments[attendance.id]
            existing_payment.summ = summ
            existing_payment.cashier = cashier
            existing_payment.summ_date = summ_date
            existing_payment.is_pay = True
            existing_payment.save()
            payments_to_update.append(existing_payment)
        else:
            # ✅ СОЗДАЕМ НОВУЮ ЗАПИСЬ С ПРИВЯЗКОЙ К ПОСЕЩЕНИЮ
            payments_to_create.append(
                CustumerSubscriptonPayment(
                    custumer=customer,
                    groups=group,
                    attendance_record=attendance,  # ✅ ПРИВЯЗКА
                    subscription=None,
                    summ=summ,
                    summ_date=summ_date,
                    cashier=cashier,
                    sub_date=attendance.date,
                    is_pay=True,
                    company=company,
                    owner=owner,
                )
            )

    if payments_to_create:
        CustumerSubscriptonPayment.objects.bulk_create(payments_to_create)

    return payments_to_create, payments_to_update


@transaction.atomic
def forgive_attendances(
    customer: Custumer,
    group: GroupsClass,
    attendance_ids: List[int],
    company,
    owner,
) -> Dict[str, any]:
    """
    Прощение (бесплатная оплата) посещений.

    Args:
        customer: Клиент
        group: Группа
        attendance_ids: Список ID посещений для прощения
        company: Компания
        owner: Владелец

    Returns:
        Словарь с результатом операции
    """
    # Получаем посещения
    attendances = GroupClassessCustumer.objects.filter(id__in=attendance_ids)

    # Помечаем как оплаченные (заблокированные)
    attendances.update(is_block=True, used_subscription=None)

    # ✅ Получаем существующие записи по attendance_record (приоритет)
    existing_payments_by_attendance = {
        payment.attendance_record_id: payment
        for payment in CustumerSubscriptonPayment.objects.filter(
            attendance_record_id__in=attendance_ids,
            subscription=None,
        )
    }

    # Получаем даты посещений
    payment_dates = [attendance.date for attendance in attendances]

    # ✅ Также ищем по датам для совместимости
    # (старые записи без attendance_record)
    existing_payments_by_date = {}
    for payment in CustumerSubscriptonPayment.objects.filter(
        custumer=customer,
        groups=group,
        sub_date__in=payment_dates,
        subscription=None,
        attendance_record__isnull=True,  # Только без связи
    ).order_by("sub_date", "-id"):
        if payment.sub_date not in existing_payments_by_date:
            existing_payments_by_date[payment.sub_date] = payment

    payments_to_create = []
    payments_to_update = []

    for attendance in attendances:
        # ✅ Приоритет: ищем по attendance_record
        if attendance.id in existing_payments_by_attendance:
            existing_payment = existing_payments_by_attendance[attendance.id]
            existing_payment.summ = 0  # Прощено - сумма 0
            existing_payment.cashier = None
            existing_payment.summ_date = date.today()
            existing_payment.is_pay = True
            existing_payment.attendance_record = attendance
            existing_payment.save()
            payments_to_update.append(existing_payment)
        elif attendance.date in existing_payments_by_date:
            # Обновляем существующую запись (старый формат)
            existing_payment = existing_payments_by_date[attendance.date]
            existing_payment.summ = 0  # Прощено - сумма 0
            existing_payment.cashier = None
            existing_payment.summ_date = date.today()
            existing_payment.is_pay = True
            existing_payment.attendance_record = attendance
            existing_payment.save()
            payments_to_update.append(existing_payment)
        else:
            # Создаем новую запись
            payments_to_create.append(
                CustumerSubscriptonPayment(
                    custumer=customer,
                    groups=group,
                    attendance_record=attendance,
                    subscription=None,
                    summ=0,  # Прощено - сумма 0
                    summ_date=date.today(),
                    cashier=None,
                    sub_date=attendance.date,
                    is_pay=True,
                    company=company,
                    owner=owner,
                )
            )

    if payments_to_create:
        # Используем bulk_create для создания записей
        CustumerSubscriptonPayment.objects.bulk_create(
            payments_to_create, ignore_conflicts=True
        )

    return {
        "success": True,
        "attendances_count": len(attendance_ids),
        "created_payments": len(payments_to_create),
        "updated_payments": len(payments_to_update),
    }


@transaction.atomic
def process_subscription_payment(
    customer: Custumer,
    group: GroupsClass,
    attendance_ids: List[int],
    subscription_id: int,
) -> Dict[str, any]:
    """
    Обработка списания посещений с абонемента.

    Args:
        customer: Клиент
        group: Группа
        attendance_ids: Список ID посещений для списания
        subscription_id: ID абонемента

    Returns:
        Словарь с результатом операции

    Raises:
        ValueError: Если абонемент не найден или недостаточно занятий
    """
    subscription = (
        CustumerSubscription.objects.select_for_update()
        .filter(id=subscription_id, is_blok=False)
        .first()
    )

    if not subscription:
        raise ValueError("Абонемент не найден!")

    # Получаем посещения с датами
    attendances = GroupClassessCustumer.objects.filter(
        id__in=attendance_ids,
        is_block=False,
    ).values_list("id", "date")

    attendance_dates = []
    invalid_dates = []

    # Проверяем даты посещений
    for att_id, att_date in attendances:
        attendance_dates.append(att_date)

        # Проверяем, входит ли дата в период действия абонемента
        if subscription.start_date and att_date < subscription.start_date:
            start_str = subscription.start_date.strftime("%d.%m.%Y")
            invalid_dates.append(
                f"{att_date.strftime('%d.%m.%Y')} "
                f"(до начала абонемента {start_str})"
            )
        elif subscription.end_date and att_date > subscription.end_date:
            end_str = subscription.end_date.strftime("%d.%m.%Y")
            invalid_dates.append(
                f"{att_date.strftime('%d.%m.%Y')} "
                f"(после окончания абонемента {end_str})"
            )

    # Если есть занятия вне периода действия абонемента
    if invalid_dates:
        raise ValueError(
            f"Невозможно списать занятия, которые не входят в период "
            f"действия абонемента: {', '.join(invalid_dates)}"
        )

    # Проверяем, является ли абонемент безлимитным
    if subscription.unlimited:
        # Атомарное обновление с использованием Coalesce
        # для обработки NULL значений
        CustumerSubscription.objects.filter(pk=subscription.pk).update(
            remained=Coalesce(F("remained"), Value(0)) + len(attendance_ids)
        )
        subscription.refresh_from_db()
    else:
        # Для обычного абонемента проверяем количество оставшихся занятий
        remained = (
            int(subscription.remained)
            if subscription.remained not in [None, "None", ""]
            else 0
        )
        num = int(subscription.number_classes or 0) - remained
        len_payment = len(attendance_ids)

        if len_payment > num:
            raise ValueError("Недостаточно занятий в абонементе!")

        # Атомарное обновление с использованием Coalesce
        # для обработки NULL значений
        CustumerSubscription.objects.filter(pk=subscription.pk).update(
            remained=Coalesce(F("remained"), Value(0)) + len_payment
        )
        subscription.refresh_from_db()

    # Обновляем все посещения одним запросом
    GroupClassessCustumer.objects.filter(id__in=attendance_ids).update(
        used_subscription=subscription,
        is_block=True,
    )

    # Удаляем только платежи для конкретных дат посещений
    if attendance_dates:
        CustumerSubscriptonPayment.objects.filter(
            groups_id=group.id,
            custumer_id=customer.id,
            sub_date__in=attendance_dates,
        ).delete()

    return {
        "success": True,
        "subscription": subscription,
        "attendances_count": len(attendance_ids),
    }


@transaction.atomic
def process_free_attendances(
    customer: Custumer,
    group: GroupsClass,
    attendance_ids: List[int],
) -> Dict[str, any]:
    """
    Обработка прощения посещений (бесплатное посещение).

    Args:
        customer: Клиент
        group: Группа
        attendance_ids: Список ID посещений для прощения

    Returns:
        Словарь с результатом операции
    """
    # Удаляем все связанные платежи
    attendance_dates = list(
        GroupClassessCustumer.objects.filter(id__in=attendance_ids)
        .values_list("date", flat=True)
        .distinct()
    )

    # Удаляем только платежи для конкретных дат
    if attendance_dates:
        CustumerSubscriptonPayment.objects.filter(
            attendance_record_id__in=attendance_ids,  # ✅ По ID посещения
            custumer_id=customer.id,
        ).delete()

    return {
        "success": True,
        "attendances_count": len(attendance_ids),
    }


def get_available_subscriptions_for_group(
    customer_id: int,
    group_id: int,
) -> QuerySet[CustumerSubscription]:
    """
    Получить доступные абонементы клиента для группы.

    Args:
        customer_id: ID клиента
        group_id: ID группы

    Returns:
        QuerySet доступных абонементов
    """
    return CustumerSubscription.objects.filter(
        custumer_id=customer_id,
        is_blok=False,
        groups=group_id,
        end_date__gte=date.today(),
    ).select_related("custumer", "owner")


def get_cashiers_for_company(company) -> List[Cashier]:
    """
    Получить кассиров для компании с кешированием.

    Args:
        company: Компания

    Returns:
        Список кассиров из кеша
    """
    return get_cached_cashiers(company.id)


def get_unpaid_attendances_summary_by_company(
    company_id: int,
) -> List[Dict]:
    """
    Получить сводку по неоплаченным посещениям всех клиентов компании.
    С кешированием в Redis на 3 минуты.

    Считает неоплаченные посещения через два сценария:
    1. Посещения без абонемента (used_subscription is NULL)
    2. Посещения с неоплаченным абонементом
       (used_subscription.attendance_status='unpaid')

    Args:
        company_id: ID компании

    Returns:
        Список словарей с информацией о клиентах и количестве
        неоплаченных посещений
        [
            {
                'custumer_id': int,
                'custumer__full_name': str,
                'groups_id': int,
                'groups_name': str,
                'count': int
            },
            ...
        ]
    """
    cache_key = f"company:{company_id}:unpaid_attendances_summary"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # Используем подзапрос для исключения прощенных посещений
    forgiven_attendance_ids = CustumerSubscriptonPayment.objects.filter(
        attendance_record__custumer__company_id=company_id,
        attendance_record__attendance_status__in=ATTENDED_STATUSES,
        subscription__isnull=True,
        is_pay=True,
        summ=0,
    ).values_list("attendance_record_id", flat=True)

    unpaid_summary = (
        GroupClassessCustumer.objects.filter(
            custumer__company_id=company_id,
            attendance_status__in=ATTENDED_STATUSES,
            is_block=False,  # Прощенные имеют is_block=True
        )
        .filter(
            Q(used_subscription__isnull=True)  # Без абонемента
            | Q(
                used_subscription__attendance_status="unpaid"
            )  # Неоплаченный абонемент
        )
        .exclude(
            used_subscription__attendance_status="none"  # Исключаем бесплатные абонементы
        )
        # Исключаем прощенные посещения (через подзапрос)
        .exclude(id__in=forgiven_attendance_ids)
        .values(
            "custumer_id",
            "custumer__full_name",
            "gr_class__groups_id",
            "gr_class__groups_id__name",
        )
        .annotate(count=Count("id"))
        .order_by("custumer__full_name")
    )

    result = list(unpaid_summary)
    cache.set(cache_key, result, CACHE_TIMEOUTS["unpaid_summary"])
    return result


def get_unpaid_count_for_customer_in_group(
    customer_id: int,
    group_id: int,
) -> int:
    """
    Получить количество неоплаченных посещений клиента в конкретной группе.

    Args:
        customer_id: ID клиента
        group_id: ID группы

    Returns:
        Количество неоплаченных посещений
    """
    # Используем подзапрос для исключения прощенных посещений
    forgiven_attendance_ids = CustumerSubscriptonPayment.objects.filter(
        attendance_record__custumer_id=customer_id,
        attendance_record__gr_class__groups_id=group_id,
        attendance_record__attendance_status__in=ATTENDED_STATUSES,
        subscription__isnull=True,
        is_pay=True,
        summ=0,
    ).values_list("attendance_record_id", flat=True)

    return (
        GroupClassessCustumer.objects.filter(
            custumer_id=customer_id,
            gr_class__groups_id=group_id,
            attendance_status__in=ATTENDED_STATUSES,
            is_block=False,  # Прощенные имеют is_block=True
        )
        .filter(
            Q(used_subscription__isnull=True)
            | Q(used_subscription__attendance_status="unpaid")
        )
        .exclude(
            used_subscription__attendance_status="none"  # Исключаем бесплатные абонементы
        )
        # Исключаем прощенные посещения (через подзапрос)
        .exclude(id__in=forgiven_attendance_ids)
        .count()
    )
