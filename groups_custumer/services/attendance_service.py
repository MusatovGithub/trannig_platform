"""
Сервисный слой для работы с посещаемостью и оценками.
"""

from datetime import date
from typing import Dict, Optional

from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Coalesce

from custumer.models import (
    ATTENDANCE_SCORE,
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from groups_custumer.models import GroupClassessCustumer, GroupsClass


class AttendanceValidationError(Exception):
    """Исключение для ошибок валидации посещаемости."""

    pass


class AttendanceBlockedError(Exception):
    """Исключение для блокированных записей посещаемости."""

    pass


ATTENDED_STATUSES = [
    "attended_2",
    "attended_3",
    "attended_4",
    "attended_5",
    "attended_10",
]

VALID_STATUSES = ATTENDED_STATUSES + ["none", "not_attended"]


def validate_attendance_status(status: str) -> None:
    """
    Валидация статуса посещаемости.

    Args:
        status: Статус посещаемости

    Raises:
        AttendanceValidationError: Если статус невалидный
    """
    if status not in VALID_STATUSES:
        raise AttendanceValidationError(
            f"Невалидный статус: {status}. "
            f"Допустимые значения: {', '.join(VALID_STATUSES)}"
        )


@transaction.atomic
def update_customer_balance(
    custumer: Custumer, old_status: str, new_status: str
) -> None:
    """
    Обновление баланса клиента при изменении статуса посещаемости.

    Args:
        custumer: Клиент
        old_status: Старый статус посещаемости
        new_status: Новый статус посещаемости

    Raises:
        ValueError: Если недостаточно баллов для списания
    """
    old_score = ATTENDANCE_SCORE.get(old_status, 0)
    new_score = ATTENDANCE_SCORE.get(new_status, 0)

    # Если статус не изменился — ничего не делаем
    if old_score == new_score:
        return

    delta = new_score - old_score

    # Если снимаем баллы, но баланс не хватает — не даём уйти в минус
    if delta < 0 and custumer.balance < abs(delta):
        raise ValueError("Недостаточно баллов для списания!")

    # Атомарное обновление
    Custumer.objects.filter(pk=custumer.pk).update(
        balance=F("balance") + delta
    )


def find_and_use_subscription(
    custumer: Custumer,
    group: GroupsClass,
    day_date: date,
) -> Optional[CustumerSubscription]:
    """
    Поиск и использование подходящей подписки.

    Args:
        custumer: Клиент
        group: Группа
        day_date: Дата занятия

    Returns:
        Использованная подписка или None, если подходящей не найдено
    """
    # Проверяем, есть ли предзагруженные подписки
    if hasattr(custumer, "prefetched_subscriptions"):
        candidate_ids = []
        for sub in custumer.prefetched_subscriptions:
            start_date_ok = (
                sub.start_date is None or sub.start_date <= day_date
            )
            end_date_ok = sub.end_date is None or sub.end_date >= day_date

            if start_date_ok and end_date_ok:
                group_ids = [g.id for g in sub.groups.all()]
                if group.id in group_ids:
                    candidate_ids.append(sub.id)

        # Блокируем только найденные подписки одним запросом
        if candidate_ids:
            subscriptions = (
                CustumerSubscription.objects.filter(id__in=candidate_ids)
                .select_for_update()
                .order_by("start_date")
            )
        else:
            return None
    else:
        # Fallback: если подписки не предзагружены, делаем запрос
        subscriptions = list(
            CustumerSubscription.objects.filter(
                custumer=custumer,
                groups=group,
                start_date__lte=day_date,
                end_date__gte=day_date,
            )
            .select_for_update()
            .order_by("start_date")
        )

    for subscription in subscriptions:
        if subscription.remained is None:
            subscription.remained = 0

        if (
            subscription.number_classes is None
            or subscription.remained < subscription.number_classes
        ):
            CustumerSubscription.objects.filter(id=subscription.id).update(
                remained=Coalesce(F("remained"), Value(0)) + 1,
                updated_at=day_date,
            )
            subscription.refresh_from_db()
            return subscription

    return None


def create_payment_record(
    custumer: Custumer,
    group: GroupsClass,
    day_date: date,
    attendance: GroupClassessCustumer,
    company,
    owner,
) -> None:
    """
    Создание записи оплаты при отсутствии подписки.

    Args:
        custumer: Клиент
        group: Группа
        day_date: Дата занятия
        company: Компания
        owner: Владелец (пользователь)
    """
    CustumerSubscriptonPayment.objects.get_or_create(
        custumer=custumer,
        groups=group,
        subscription=None,
        summ=0,
        sub_date=day_date,
        attendance_record=attendance,
        defaults={
            "cashier": None,
            "count": 1,
            "is_blok": False,  # Не оплачено, требует оплаты
            "is_pay": False,  # Не оплачено
            "company": company,
            "owner": owner,
        },
    )


def return_subscription_usage(
    used_subscription: Optional[CustumerSubscription],
) -> None:
    """
    Возврат использования подписки.

    Args:
        used_subscription: Использованная подписка
    """
    if used_subscription:
        used_subscription.remained = used_subscription.remained or 0
        if used_subscription.remained > 0:
            CustumerSubscription.objects.filter(
                id=used_subscription.id
            ).update(remained=Coalesce(F("remained"), Value(0)) - 1)
            used_subscription.refresh_from_db()


def delete_payment_record(
    custumer: Custumer,
    group: GroupsClass,
    day_date: date,
) -> None:
    """
    Удаление записи оплаты.

    Args:
        custumer: Клиент
        group: Группа
        day_date: Дата занятия
    """
    CustumerSubscriptonPayment.objects.filter(
        custumer=custumer,
        groups=group,
        sub_date=day_date,
        subscription=None,
    ).delete()


@transaction.atomic
def process_attendance_mark(
    attendance: GroupClassessCustumer,
    new_status: str,
    comment: Optional[str],
    company,
    owner,
) -> Dict[str, any]:
    """
    Обработка выставления оценки посещаемости.

    Args:
        attendance: Запись посещаемости
        new_status: Новый статус
        comment: Комментарий (опционально)
        company: Компания
        owner: Владелец (пользователь)

    Returns:
        Словарь с результатом операции

    Raises:
        AttendanceValidationError: При невалидных данных
        ValueError: При проблемах с балансом
    """
    # Валидация
    validate_attendance_status(new_status)

    custumer = attendance.custumer
    group = attendance.gr_class.groups_id
    day_date = attendance.date
    old_status = attendance.attendance_status

    # Обновление баланса клиента
    update_customer_balance(custumer, old_status, new_status)

    used_subscription = None

    action = "set_grade"

    # Обработка посещения с оценкой
    if new_status in ATTENDED_STATUSES:
        action = "set_grade"

        # Поиск и использование подписки ТОЛЬКО если ещё не оплачено
        if not attendance.is_block and not attendance.used_subscription:
            used_subscription = find_and_use_subscription(
                custumer, group, day_date
            )
            if used_subscription:
                CustumerSubscriptonPayment.objects.filter(
                    attendance_record=attendance,
                    subscription=None,
                    is_pay=False,
                ).delete()
        else:
            # Если уже оплачено - сохраняем существующее состояние
            used_subscription = attendance.used_subscription

        # Обновление записи посещаемости
        attendance.attendance_status = new_status
        attendance.used_subscription = used_subscription
        # is_block остается как есть, если уже оплачено
        # иначе блокируем только если нашли абонемент
        if not attendance.is_block:
            attendance.is_block = bool(used_subscription)
        if comment is not None:
            attendance.comment = comment
        attendance.company = company
        attendance.owner = owner
        attendance.save()

    # Обработка отсутствия или сброса оценки
    elif new_status in ["none", "not_attended"]:
        action = "reset" if new_status == "none" else "set_absent"
        # Если раньше была оценка, возвращаем подписку/удаляем оплату
        if old_status in ATTENDED_STATUSES:
            old_subscription = attendance.used_subscription
            return_subscription_usage(old_subscription)
            delete_payment_record(custumer, group, day_date)

        # Обновление записи посещаемости
        attendance.attendance_status = new_status
        attendance.used_subscription = None
        attendance.is_block = False  # Разблокируем при сбросе оценки
        if comment is not None:
            attendance.comment = comment
        attendance.company = company
        attendance.owner = owner
        attendance.save()

    return {
        "success": True,
        "attendance_id": attendance.id,
        "new_status": new_status,
        "comment": attendance.comment,
        "action": action,
        "used_subscription_id": (
            attendance.used_subscription.id
            if attendance.used_subscription
            else None
        ),
    }


def get_attendance_display_text(status: str) -> str:
    """
    Получение текста для отображения статуса посещаемости.

    Args:
        status: Статус посещаемости

    Returns:
        Текст для отображения
    """
    display_map = {
        "attended_2": "2",
        "attended_3": "3",
        "attended_4": "4",
        "attended_5": "5",
        "attended_10": "10",
        "not_attended": "Н",
        "none": "+",
    }
    return display_map.get(status, status)


def get_attendance_css_class(status: str) -> str:
    """
    Получение CSS класса для статуса посещаемости.

    Args:
        status: Статус посещаемости

    Returns:
        CSS класс
    """
    class_map = {
        "attended_2": "grade-2",
        "attended_3": "grade-3",
        "attended_4": "grade-4",
        "attended_5": "grade-5",
        "attended_10": "grade-10",
        "not_attended": "status-absent",
        "none": "status-empty",
    }
    return class_map.get(status, "status-empty")
