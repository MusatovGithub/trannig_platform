import logging
from datetime import date, datetime
from typing import Iterable, Optional, Sequence, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from custumer.models import (
    Cashier,
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
    SubscriptionTemplate,
)
from custumer.utils import get_user_permissions
from groups_custumer.models import GroupClassessCustumer, GroupsClass

logger = logging.getLogger(__name__)


def create_subscription_with_payment(
    custumer,
    groups,
    number,
    start_date,
    end_date,
    unlimited,
    is_free,
    price,
    summ,
    cashier_id,
    date_summ,
    company,
    owner,
):
    """
    Общая функция для создания абонемента с платежом.

    Args:
        custumer: Клиент
        groups: Группы (QuerySet или список)
        number: Количество занятий
        start_date: Дата начала
        end_date: Дата окончания
        unlimited: Безлимитный
        is_free: Бесплатный
        price: Стоимость абонемента
        summ: Сумма платежа
        cashier_id: ID кассира
        date_summ: Дата платежа
        company: Компания
        owner: Владелец

    Returns:
        tuple: (subscription, payments_created)
    """
    # Определяем статус посещения
    if is_free:
        attendance_status = "none"
    else:
        attendance_status = "paid" if summ == price else "unpaid"
    if not price:
        price = 0

    # Создаем абонемент
    subscription = CustumerSubscription.objects.create(
        custumer=custumer,
        number_classes=number,
        start_date=start_date,
        end_date=end_date,
        unlimited=unlimited,
        is_free=is_free,
        total_cost=price,  # Стоимость абонемента
        attendance_status=attendance_status,
        company=company,
        owner=owner,
    )

    # Привязываем группы
    if isinstance(groups, (list, tuple)):
        subscription.groups.set(groups)
    else:
        subscription.groups.set(groups)

    payments_created = []

    # Создаем платежи если абонемент не бесплатный
    if not is_free and summ and cashier_id:
        cashier = get_object_or_404(Cashier, id=cashier_id)
        summ_date = (
            datetime.strptime(date_summ, "%d.%m.%Y").date()
            if date_summ
            else None
        )

        # Создаем платеж для каждой группы
        payments_created = []
        for group in groups:
            payments_created.append(
                CustumerSubscriptonPayment(
                    custumer=custumer,
                    groups=group,
                    subscription=subscription,
                    summ=summ,  # Сумма платежа
                    summ_date=summ_date,
                    cashier=cashier,
                    count=None,
                    is_blok=False,
                    is_pay=True,
                    company=company,
                    owner=owner,
                )
            )
        CustumerSubscriptonPayment.objects.bulk_create(payments_created)

    return subscription, payments_created


def ensure_can_add_subscription(user) -> bool:
    """
    Проверяет, может ли пользователь добавлять абонементы.
    """

    if user.groups.filter(name="admin").exists():
        return True

    user_permissions = get_user_permissions(user)
    return user_permissions.get("can_add_subscriptions", False)


def prepare_subscription_form_context(
    *,
    request,
    custumer: Custumer,
    groups_qs,
    allow_group_selection: bool,
    cancel_url: str,
    form_data: Optional[dict] = None,
    extra_context: Optional[dict] = None,
):
    """
    Готовит базовый контекст для формы выдачи абонемента.
    """

    context = {
        "custumer": custumer,
        "temp": SubscriptionTemplate.objects.filter(
            company=request.user.company
        ),
        "cashier": Cashier.objects.filter(company=request.user.company),
        "allow_group_selection": allow_group_selection,
        "cancel_url": cancel_url,
        "user_permissions": get_user_permissions(request.user),
    }

    if allow_group_selection:
        context["groups"] = groups_qs
    else:
        context["fixed_groups"] = list(groups_qs)

    default_form_data = {
        "number": "",
        "start_date": "",
        "end_date": "",
        "unlimited": False,
        "is_free": False,
        "price": "",
        "summ": "",
        "cashier": "",
        "date_summ": "",
        "group_ids": [],
        "auto_bind_attendances": True,
    }

    context["form_data"] = {**default_form_data, **(form_data or {})}

    if extra_context:
        context.update(extra_context)

    return context


def _parse_posted_dates(
    start_date_raw: str, end_date_raw: str
) -> Tuple[date, date]:
    """
    Преобразует строки дат в объект date.
    """

    try:
        start_date = datetime.strptime(start_date_raw, "%d.%m.%Y").date()
        end_date = datetime.strptime(end_date_raw, "%d.%m.%Y").date()
    except (TypeError, ValueError):
        raise ValidationError(
            "Некорректный формат даты. Ожидается дд.мм.гггг."
        )

    return start_date, end_date


def _collect_groups(
    *,
    groups_qs,
    group_ids: Sequence[str],
    allow_group_selection: bool,
) -> Iterable[GroupsClass]:
    """
    Получает группы, выбранные пользователем.
    """

    if allow_group_selection:
        if not group_ids:
            raise ValidationError("Пожалуйста, заполните все поля!")

        selected_groups = groups_qs.filter(id__in=group_ids)
        if not selected_groups.exists():
            raise ValidationError("Выбранные группы недоступны.")
        return selected_groups

    return groups_qs


def _build_form_data(request) -> dict:
    """
    Собирает данные формы из request.POST.
    """

    return {
        "number": request.POST.get("number", ""),
        "start_date": request.POST.get("start_date", ""),
        "end_date": request.POST.get("end_date", ""),
        "unlimited": "unlimited" in request.POST,
        "is_free": "is_free" in request.POST,
        "price": request.POST.get("price", ""),
        "summ": request.POST.get("summ", ""),
        "cashier": request.POST.get("cashier", ""),
        "date_summ": request.POST.get("date_summ", ""),
        "group_ids": request.POST.getlist("group"),
        "auto_bind_attendances": "auto_bind_attendances" in request.POST,
    }


def process_subscription_submission(
    *,
    request,
    custumer: Custumer,
    groups_qs,
    allow_group_selection: bool,
):
    """
    Обрабатывает отправку формы выдачи абонемента.
    Возвращает кортеж (success, payload).
    """

    form_data = _build_form_data(request)

    start_raw = form_data["start_date"]
    end_raw = form_data["end_date"]

    if not start_raw or not end_raw:
        return False, {
            "error": "Пожалуйста, заполните все поля!",
            "form_data": form_data,
        }

    try:
        selected_groups = _collect_groups(
            groups_qs=groups_qs,
            group_ids=form_data["group_ids"],
            allow_group_selection=allow_group_selection,
        )
    except ValidationError as exc:
        return False, {"error": str(exc), "form_data": form_data}

    try:
        start_date, end_date = _parse_posted_dates(start_raw, end_raw)
    except ValidationError as exc:
        return False, {"error": str(exc), "form_data": form_data}

    existing_subscription = CustumerSubscription.objects.filter(
        custumer=custumer,
        groups__in=selected_groups,
        start_date__lte=end_date,
        end_date__gte=start_date,
        is_blok=False,
    ).exists()

    if existing_subscription:
        return False, {
            "error": (
                "B этом диапазоне уже есть абонемент! "
                "Пожалуйста, выберите другие даты. "
                f"{end_date} - с этого момента вы можете выбрать следующие дни"
            ),
            "form_data": form_data,
        }

    number = form_data["number"] or None
    unlimited = form_data["unlimited"]
    is_free = form_data["is_free"]
    price = form_data["price"]
    summ = form_data["summ"]
    cashier_id = form_data["cashier"] or None
    date_summ = form_data["date_summ"]
    auto_bind_attendances = form_data.get("auto_bind_attendances", False)

    with transaction.atomic():
        subscription, payments = create_subscription_with_payment(
            custumer=custumer,
            groups=selected_groups,
            number=number,
            start_date=start_date,
            end_date=end_date,
            unlimited=unlimited,
            is_free=is_free,
            price=price,
            summ=summ,
            cashier_id=cashier_id,
            date_summ=date_summ,
            company=request.user.company,
            owner=request.user,
        )

        # Запуск автопривязки посещений если активирован флаг
        if auto_bind_attendances:
            from custumer.tasks import (
                auto_bind_attendances_to_subscription,
                recalculate_subscription_payment_status,
            )

            def bind_and_recalculate():
                # Сначала привязываем посещения
                auto_bind_attendances_to_subscription.delay(
                    subscription_id=subscription.id
                )
                # Затем пересчитываем статус оплаты (важно для бесплатных абонементов)
                recalculate_subscription_payment_status.delay(
                    subscription_id=subscription.id
                )

            transaction.on_commit(bind_and_recalculate)

    return True, {
        "subscription": subscription,
        "payments": payments,
    }


def validate_subscription_update(
    group_ids: list,
    start_date: str,
    end_date: str,
    number: Optional[str] = None,
    unlimited: bool = False,
    subscription_id: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Валидация данных обновления абонемента.

    Args:
        group_ids: Список ID групп
        start_date: Дата начала (строка)
        end_date: Дата окончания (строка)
        number: Количество занятий
        unlimited: Безлимитный абонемент
        subscription_id: ID абонемента (для проверки remained)

    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    # Проверка обязательных полей
    if not group_ids or not start_date or not end_date:
        return False, "Пожалуйста, заполните все обязательные поля!"

    # Валидация дат
    try:
        start = datetime.strptime(start_date, "%d.%m.%Y").date()
        end = datetime.strptime(end_date, "%d.%m.%Y").date()

        if start >= end:
            return False, "Дата начала должна быть раньше даты окончания!"
    except ValueError:
        return False, "Неверный формат даты!"

    # Проверка количества занятий для не безлимитного абонемента
    if not unlimited and number:
        try:
            num_classes = int(number)
            if num_classes <= 0:
                return False, "Количество занятий должно быть больше 0!"
        except (ValueError, TypeError):
            return False, "Неверное количество занятий!"

    # Валидация безлимитного абонемента
    if unlimited and number:
        return (
            False,
            "Безлимитный абонемент не может иметь количество занятий!",
        )

    if not unlimited and not number:
        return False, "Укажите количество занятий или выберите безлимитный!"

    # Проверка уменьшения number_classes (не должно быть меньше remained)
    if not unlimited and number and subscription_id:
        try:
            new_number = int(number)
            subscription = CustumerSubscription.objects.get(pk=subscription_id)
            current_remained = subscription.remained or 0

            if current_remained > new_number:
                return False, (
                    f"Невозможно уменьшить количество занятий! "
                    f"Уже использовано {current_remained} из {subscription.number_classes}. "
                    f"Минимальное значение: {current_remained}"
                )
        except CustumerSubscription.DoesNotExist:
            # Если абонемент не найден, просто пропускаем эту проверку
            pass
        except (ValueError, TypeError):
            # Если не удалось преобразовать в int, ошибка уже была выше
            pass

    return True, None


def validate_subscription_dates(
    subscription_id: int,
    new_start_date: date,
    new_end_date: date,
) -> dict:
    """
    Проверка возможности изменения дат абонемента.

    Args:
        subscription_id: ID абонемента
        new_start_date: Новая дата начала
        new_end_date: Новая дата окончания

    Returns:
        Dict с результатом валидации
    """
    # Проверяем посещения вне нового диапазона
    out_of_range = GroupClassessCustumer.objects.filter(
        used_subscription_id=subscription_id,
    ).filter(Q(date__lt=new_start_date) | Q(date__gt=new_end_date))

    count = out_of_range.count()
    if count > 0:
        return {
            "valid": False,
            "error": (
                f"Невозможно изменить даты! {count} посещений "
                f"выпадают из нового диапазона. "
                f"Сначала обработайте эти посещения."
            ),
            "out_of_range_count": count,
        }

    return {"valid": True}


@transaction.atomic
def update_subscription_groups(
    subscription_id: int,
    new_group_ids: list,
) -> dict:
    """
    Обработка изменения групп с защитой от race condition.

    Args:
        subscription_id: ID абонемента
        new_group_ids: Список новых ID групп

    Returns:
        Dict с информацией об изменениях
    """
    # Блокировка подписки
    subscription = CustumerSubscription.objects.select_for_update().get(
        pk=subscription_id
    )

    old_groups = set(subscription.groups.values_list("id", flat=True))
    new_groups = set(new_group_ids)
    removed_groups = old_groups - new_groups

    if removed_groups:
        # Атомарный подсчет затронутых посещений
        affected_count = GroupClassessCustumer.objects.filter(
            used_subscription=subscription,
            gr_class__groups_id__in=removed_groups,
            is_block=False,
        ).count()

        logger.info(
            f"Subscription {subscription_id} groups changed. "
            f"Removed groups: {removed_groups}, affected attendances: {affected_count}"
        )

        # Возвращаем информацию для запуска Celery задачи
        return {
            "has_changes": True,
            "affected_count": affected_count,
            "removed_groups": list(removed_groups),
        }

    return {"has_changes": False}


@transaction.atomic
def update_subscription_core(
    subscription_id: int,
    data: dict,
) -> tuple:
    """
    Основное обновление данных абонемента с блокировкой.

    Args:
        subscription_id: ID абонемента
        data: Словарь с данными для обновления

    Returns:
        Tuple: (обновленный абонемент, изменились ли даты)
    """
    # Блокируем подписку для атомарного обновления
    subscription = CustumerSubscription.objects.select_for_update().get(
        pk=subscription_id
    )

    # Проверяем, изменились ли даты
    old_start = subscription.start_date
    old_end = subscription.end_date
    new_start = data["start_date"]
    new_end = data["end_date"]

    dates_changed = old_start != new_start or old_end != new_end

    # Атомарное обновление полей
    CustumerSubscription.objects.filter(pk=subscription_id).update(
        number_classes=data.get("number"),
        start_date=data["start_date"],
        end_date=data["end_date"],
        unlimited=data["unlimited"],
        is_free=data["is_free"],
        total_cost=data.get("price", 0),
        attendance_status=data["attendance_status"],
    )

    subscription.refresh_from_db()
    subscription.groups.set(data["group_ids"])

    logger.info(
        f"Subscription {subscription_id} core data updated. "
        f"Dates changed: {dates_changed}, unlimited: {data['unlimited']}"
    )

    return subscription, dates_changed


@transaction.atomic
def update_subscription_payments(
    subscription_id: int,
    customer_id: int,
    group_ids: list,
    payment_data: dict,
) -> list:
    """
    Обновление платежей по абонементу.

    Args:
        subscription_id: ID абонемента
        customer_id: ID клиента
        group_ids: Список ID групп
        payment_data: Данные платежа

    Returns:
        Список созданных/обновленных платежей
    """
    subscription = CustumerSubscription.objects.select_for_update().get(
        pk=subscription_id
    )

    custumer = get_object_or_404(Custumer, id=customer_id)

    if subscription.is_free:
        # Удаляем все платежи для бесплатного абонемента
        CustumerSubscriptonPayment.objects.filter(
            subscription_id=subscription_id
        ).delete()
        return []

    # Обрабатываем платные абонементы
    payments = []
    if payment_data.get("summ") and payment_data.get("cashier_id"):
        cashier = get_object_or_404(Cashier, id=payment_data["cashier_id"])
        summ_date = (
            datetime.strptime(payment_data["date_summ"], "%d.%m.%Y").date()
            if payment_data.get("date_summ")
            else None
        )

        groups = GroupsClass.objects.filter(id__in=group_ids)

        for group in groups:
            payment, created = (
                CustumerSubscriptonPayment.objects.update_or_create(
                    subscription=subscription,
                    custumer=custumer,
                    groups=group,
                    defaults={
                        "summ": payment_data["summ"],
                        "summ_date": summ_date,
                        "cashier": cashier,
                        "company": subscription.company,
                        "owner": subscription.owner,
                    },
                )
            )
            payments.append(payment)

    return payments
