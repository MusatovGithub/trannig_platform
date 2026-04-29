from __future__ import annotations

import logging
from typing import Dict, List, Optional

from celery import shared_task
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Coalesce

from custumer.models import (
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from custumer.payment.services import ATTENDED_STATUSES
from groups_custumer.models import GroupClasses, GroupClassessCustumer

logger = logging.getLogger(__name__)


@shared_task
def sync_customer_attendances(customer_id: int) -> None:
    """
    Создаёт записи посещаемости клиента для всех занятий его групп.
    """
    customer = Custumer.objects.filter(id=customer_id).first()
    if not customer:
        return

    group_ids = list(customer.groups.values_list("id", flat=True))
    if not group_ids:
        return

    group_classes = GroupClasses.objects.filter(groups_id__in=group_ids)
    attendances_to_update = []

    for group_class in group_classes.iterator():
        attendance, created = GroupClassessCustumer.objects.get_or_create(
            gr_class=group_class,
            custumer=customer,
            defaults={
                "date": group_class.date,
                "company": customer.company,
                "owner": customer.owner,
                "is_none": False,
            },
        )
        if not created and attendance.is_none:
            attendance.is_none = False
            attendances_to_update.append(attendance)

    for attendance in attendances_to_update:
        attendance.save(update_fields=["is_none"])


@shared_task(bind=True, max_retries=3)
def recalculate_subscription_attendances_on_groups_change(
    self,
    subscription_id: int,
    removed_group_ids: List[int],
) -> Dict:
    """
    Пересчитывает посещения при удалении групп из абонемента.
    Идемпотентная операция: можно запускать повторно.

    Args:
        subscription_id: ID абонемента
        removed_group_ids: Список ID удаленных групп

    Returns:
        Dict с результатом операции
    """
    try:
        with transaction.atomic():
            # Блокируем подписку
            subscription = (
                CustumerSubscription.objects.select_for_update().get(
                    pk=subscription_id
                )
            )

            # Находим все затронутые посещения
            affected_attendances = GroupClassessCustumer.objects.filter(
                used_subscription=subscription,
                gr_class__groups_id__in=removed_group_ids,
                is_block=False,
            )

            attendance_list = list(affected_attendances)
            count = len(attendance_list)

            if count == 0:
                logger.info(
                    f"No attendances to process for subscription {subscription_id}"  # noqa: E501
                )
                return {"status": "no_changes", "processed": 0}

            # Атомарное уменьшение remained
            # Используем Coalesce для обработки NULL значений
            CustumerSubscription.objects.filter(pk=subscription_id).update(
                remained=Coalesce(F("remained"), Value(0)) - count
            )

            # Bulk создание записей о неоплаченных посещениях
            payments_to_create = []
            for att in attendance_list:
                payments_to_create.append(
                    CustumerSubscriptonPayment(
                        custumer=att.custumer,
                        groups=att.gr_class.groups_id,
                        sub_date=att.date,
                        subscription=None,
                        attendance_record=att,
                        summ=0,
                        is_pay=False,
                        company=subscription.company,
                        owner=subscription.owner,
                    )
                )

            # Bulk create с игнорированием дубликатов (идемпотентность)
            CustumerSubscriptonPayment.objects.bulk_create(
                payments_to_create,
                ignore_conflicts=True,
            )

            # Bulk обновление посещений
            affected_attendances.update(used_subscription=None)

            logger.info(
                f"Successfully processed {count} attendances "
                f"for subscription {subscription_id}"
            )

            return {
                "status": "success",
                "processed": count,
                "subscription_id": subscription_id,
            }

    except CustumerSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {
            "status": "error",
            "error": "Subscription not found",
        }
    except Exception as exc:
        logger.error(
            f"Error processing subscription {subscription_id}: {exc}",
            exc_info=True,
        )
        # Retry с экспоненциальной задержкой
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def recalculate_subscription_payment_status(
    self,
    subscription_id: int,
) -> Dict:
    """
    Пересчитывает статус оплаты абонемента на основе платежей.
    Идемпотентная операция.

    Args:
        subscription_id: ID абонемента

    Returns:
        Dict с результатом операции
    """
    try:
        with transaction.atomic():
            subscription = (
                CustumerSubscription.objects.select_for_update().get(
                    pk=subscription_id
                )
            )

            old_status = subscription.attendance_status

            # Вычисляем новый статус
            if subscription.is_free:
                new_status = "none"
            elif subscription.total_cost:
                total_paid = sum(
                    p.summ
                    for p in subscription.payments.all()
                    if p.summ is not None
                )
                new_status = (
                    "paid"
                    if total_paid >= subscription.total_cost
                    else "unpaid"
                )
            else:
                new_status = "unpaid"

            # Обновляем только если статус изменился
            if old_status != new_status:
                CustumerSubscription.objects.filter(pk=subscription_id).update(
                    attendance_status=new_status
                )
                logger.info(
                    f"Updated subscription {subscription_id} status: "
                    f"{old_status} -> {new_status}"
                )
                return {
                    "status": "updated",
                    "old_status": old_status,
                    "new_status": new_status,
                }
            else:
                return {
                    "status": "no_change",
                    "current_status": old_status,
                }

    except CustumerSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {
            "status": "error",
            "error": "Subscription not found",
        }
    except Exception as exc:
        logger.error(
            f"Error recalculating payment status for {subscription_id}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def auto_bind_attendances_to_subscription(
    self,
    subscription_id: int,
    old_start_date: Optional[str] = None,
    old_end_date: Optional[str] = None,
) -> Dict:
    """
    Автоматическая привязка посещений к абонементу при изменении дат.
    Идемпотентная операция: можно запускать повторно.

    Args:
        subscription_id: ID абонемента
        old_start_date: Старая дата начала (для определения новых дат)
        old_end_date: Старая дата окончания

    Returns:
        Dict с результатом операции
    """
    try:
        with transaction.atomic():
            subscription = (
                CustumerSubscription.objects.select_for_update().get(
                    pk=subscription_id
                )
            )

            # Находим непривязанные посещения в период действия абонемента
            # 1. Посещения клиента
            # 2. В группах абонемента
            # 3. В период действия абонемента
            # 4. С оценкой (attended)
            # 5. Без привязки к абонементу (used_subscription is NULL)

            candidate_attendances = GroupClassessCustumer.objects.filter(
                custumer=subscription.custumer,
                gr_class__groups_id__in=subscription.groups.all(),
                date__gte=subscription.start_date,
                date__lte=subscription.end_date,
                attendance_status__in=ATTENDED_STATUSES,
                used_subscription__isnull=True,
                is_block=False,
            )

            count = candidate_attendances.count()
            if count == 0:
                logger.info(
                    f"No unpaid attendances to bind for subscription "
                    f"{subscription_id}"
                )
                return {"status": "no_changes", "processed": 0}

            # Проверяем, хватит ли занятий в абонементе
            if not subscription.unlimited:
                remained = subscription.remained or 0
                available = (
                    subscription.number_classes - remained
                    if subscription.number_classes
                    else 0
                )
                if count > available:
                    logger.warning(
                        f"Insufficient classes in subscription "
                        f"{subscription_id}: "
                        f"available={available}, required={count}"
                    )
                    return {
                        "status": "insufficient_classes",
                        "available": available,
                        "required": count,
                    }

            # Привязываем посещения
            candidate_attendances.update(
                used_subscription=subscription,
                is_block=True,
            )

            # Обновляем счетчик абонемента
            CustumerSubscription.objects.filter(pk=subscription_id).update(
                remained=Coalesce(F("remained"), Value(0)) + count
            )

            # Для бесплатных абонементов сразу обновляем статус на "none"
            # чтобы посещения не попадали в список неоплаченных
            if subscription.is_free:
                CustumerSubscription.objects.filter(pk=subscription_id).update(
                    attendance_status="none"
                )

            # Удаляем записи о неоплаченных посещениях для этих дат
            attendance_dates = list(
                candidate_attendances.values_list("date", flat=True)
            )
            if attendance_dates:
                CustumerSubscriptonPayment.objects.filter(
                    custumer=subscription.custumer,
                    groups__in=subscription.groups.all(),
                    sub_date__in=attendance_dates,
                    subscription__isnull=True,
                ).delete()

            logger.info(
                f"Successfully bound {count} attendances to subscription "
                f"{subscription_id}"
            )

            return {
                "status": "success",
                "processed": count,
                "subscription_id": subscription_id,
            }

    except CustumerSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {
            "status": "error",
            "error": "Subscription not found",
        }
    except Exception as exc:
        logger.error(
            f"Error auto-binding attendances for {subscription_id}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


# 1. Исправление is_block - транзакция на батч
@shared_task(bind=True, max_retries=3)
def fix_attendance_blocks(
    self, company_id: Optional[int] = None, batch_size: int = 1000
) -> Dict:
    """Исправляет is_block для посещений с used_subscription."""
    queryset = GroupClassessCustumer.objects.filter(
        attendance_status__in=ATTENDED_STATUSES,
        used_subscription__isnull=False,
        is_block=False,
    )
    if company_id:
        queryset = queryset.filter(custumer__company_id=company_id)

    total = 0
    # Обрабатываем батчами с транзакцией на каждый батч
    attendance_ids = list(queryset.values_list("id", flat=True))

    for i in range(0, len(attendance_ids), batch_size):
        batch = attendance_ids[i : i + batch_size]  # noqa: E203
        # ✅ Транзакция на каждый батч
        with transaction.atomic():
            updated = GroupClassessCustumer.objects.filter(
                id__in=batch
            ).update(is_block=True)
            total += updated

    return {"status": "success", "fixed": total}


# 2. Пересчет remained - транзакция на батч абонементов
@shared_task(bind=True, max_retries=3)
def recalculate_subscription_remained(
    self,
    company_id: Optional[int] = None,
    subscription_ids: Optional[List[int]] = None,
    batch_size: int = 500,
) -> Dict:
    """Пересчитывает remained в абонементах с оптимизацией."""
    from django.db.models import Count, Q

    subscriptions_qs = CustumerSubscription.objects.filter(
        is_blok=False
    ).annotate(
        real_used_count=Count(
            "used_attendances",
            filter=Q(
                used_attendances__attendance_status__in=ATTENDED_STATUSES
            ),
        )
    )

    if company_id:
        subscriptions_qs = subscriptions_qs.filter(company_id=company_id)
    if subscription_ids:
        subscriptions_qs = subscriptions_qs.filter(id__in=subscription_ids)

    total_updated = 0

    # Обрабатываем батчами
    subscription_list = list(subscriptions_qs)
    for i in range(0, len(subscription_list), batch_size):
        batch = subscription_list[i : i + batch_size]  # noqa: E203
        to_update = []

        for sub in batch:
            if sub.unlimited:
                continue
            if sub.number_classes is not None:
                new_remained = max(0, sub.number_classes - sub.real_used_count)
                if new_remained != (sub.remained or 0):
                    sub.remained = new_remained
                    to_update.append(sub)

        # ✅ Транзакция на каждый батч
        if to_update:
            with transaction.atomic():
                CustumerSubscription.objects.bulk_update(
                    to_update, ["remained"]
                )
                total_updated += len(to_update)

    return {"status": "success", "updated": total_updated}


# 3. Обновление статусов - транзакция на батч
@shared_task(bind=True, max_retries=3)
def update_subscription_statuses(
    self,
    company_id: Optional[int] = None,
    subscription_ids: Optional[List[int]] = None,
    batch_size: int = 500,
) -> Dict:
    """Обновляет статусы абонементов на основе платежей."""
    from django.db.models import Q, Sum, Value
    from django.db.models.functions import Coalesce

    subscriptions_qs = CustumerSubscription.objects.filter(is_blok=False)

    if company_id:
        subscriptions_qs = subscriptions_qs.filter(company_id=company_id)
    if subscription_ids:
        subscriptions_qs = subscriptions_qs.filter(id__in=subscription_ids)

    # Используем annotate для подсчета суммы платежей
    subscriptions_qs = subscriptions_qs.annotate(
        total_paid=Coalesce(
            Sum("payments__summ", filter=Q(payments__summ__isnull=False)),
            Value(0),
        )
    )

    total_updated = 0
    subscription_list = list(subscriptions_qs)

    # Обрабатываем батчами
    for i in range(0, len(subscription_list), batch_size):
        batch = subscription_list[i : i + batch_size]  # noqa: E203
        to_update = []

        for sub in batch:
            if sub.is_free:
                new_status = "none"
            elif sub.total_cost:
                new_status = (
                    "paid" if sub.total_paid >= sub.total_cost else "unpaid"
                )
            else:
                new_status = "unpaid"

            if new_status != sub.attendance_status:
                sub.attendance_status = new_status
                to_update.append(sub)

        # ✅ Транзакция на каждый батч
        if to_update:
            with transaction.atomic():
                CustumerSubscription.objects.bulk_update(
                    to_update, ["attendance_status"]
                )
                total_updated += len(to_update)

    return {"status": "success", "updated": total_updated}


# 4. Создание записей оплаты - транзакция на батч
@shared_task(bind=True, max_retries=3)
def create_missing_payment_records(
    self, company_id: Optional[int] = None, batch_size: int = 500
) -> Dict:
    """Создает недостающие записи оплаты с оптимизацией."""
    unpaid_attendances = GroupClassessCustumer.objects.filter(
        attendance_status__in=ATTENDED_STATUSES,
        is_block=False,
        used_subscription__isnull=True,
    ).select_related("custumer", "gr_class__groups_id", "company", "owner")

    if company_id:
        unpaid_attendances = unpaid_attendances.filter(
            custumer__company_id=company_id
        )

    # Получаем все существующие payment_record_id одним запросом
    existing_payment_attendance_ids = set(
        CustumerSubscriptonPayment.objects.filter(
            attendance_record__isnull=False
        ).values_list("attendance_record_id", flat=True)
    )

    total_created = 0
    payments_to_create = []

    for attendance in unpaid_attendances.iterator(chunk_size=batch_size):
        if attendance.id not in existing_payment_attendance_ids:
            payments_to_create.append(
                CustumerSubscriptonPayment(
                    custumer=attendance.custumer,
                    groups=attendance.gr_class.groups_id,
                    attendance_record=attendance,
                    subscription=None,
                    summ=0,
                    sub_date=attendance.date,
                    is_pay=False,
                    is_blok=False,
                    count=1,
                    company=attendance.company,
                    owner=attendance.owner,
                )
            )

        # ✅ Транзакция на каждый батч
        if len(payments_to_create) >= batch_size:
            with transaction.atomic():
                created = CustumerSubscriptonPayment.objects.bulk_create(
                    payments_to_create, ignore_conflicts=True
                )
                total_created += len(created)
                payments_to_create = []

    # ✅ Финальная транзакция для остатка
    if payments_to_create:
        with transaction.atomic():
            created = CustumerSubscriptonPayment.objects.bulk_create(
                payments_to_create, ignore_conflicts=True
            )
            total_created += len(created)

    return {"status": "success", "created": total_created}


# 5. Удаление пустых платежей - транзакция на операцию
@shared_task(bind=True, max_retries=3)
def cleanup_empty_payments(self, company_id: Optional[int] = None) -> Dict:
    """
    Удаляет пустые платежи для посещений, оплаченных абонементом или наличными.

    ВАЖНО: НЕ затрагивает:
    - Прощенные оплаты (summ=0, is_pay=True)
    - Оплаты наличными (summ>0, is_pay=True)
    - Удаляет только пустые дубликаты (is_pay=False)
    """
    total_deleted = 0

    # 1. Пустые платежи для посещений с абонементом
    empty_payments_with_subscription = (
        CustumerSubscriptonPayment.objects.filter(
            subscription=None,
            is_pay=False,
            attendance_record__used_subscription__isnull=False,
        )
    )

    if company_id:
        empty_payments_with_subscription = (
            empty_payments_with_subscription.filter(company_id=company_id)
        )

    # ✅ Транзакция на удаление
    with transaction.atomic():
        deleted_count = empty_payments_with_subscription.delete()[0]
        total_deleted += deleted_count

    # 2. Пустые платежи для посещений, оплаченных наличными
    # ВАЖНО: Различаем прощенные (summ=0) и наличные (summ>0)
    # Удаляем пустые ТОЛЬКО для наличных, НЕ для прощенных!

    # Получаем ID посещений с оплаченными наличными (НЕ прощенные!)
    paid_cash_attendance_ids = set(
        CustumerSubscriptonPayment.objects.filter(
            subscription=None,
            is_pay=True,
            summ__gt=0,  # ✅ ТОЛЬКО наличные, НЕ прощенные (summ=0)
        ).values_list("attendance_record_id", flat=True)
    )

    if not paid_cash_attendance_ids:
        # Нет оплаченных наличными - нечего удалять
        return {"status": "success", "deleted": total_deleted}

    # Получаем пустые платежи для этих посещений
    empty_payments_with_paid = (
        CustumerSubscriptonPayment.objects.filter(
            subscription=None,
            is_pay=False,  # ✅ Только пустые
        )
        .exclude(attendance_record__isnull=True)
        .filter(
            attendance_record__is_block=True,
            attendance_record__used_subscription__isnull=True,
            attendance_record_id__in=paid_cash_attendance_ids,
            # ✅ Только для наличных
        )
    )

    if company_id:
        empty_payments_with_paid = empty_payments_with_paid.filter(
            company_id=company_id
        )

    # ✅ Транзакция на удаление
    if empty_payments_with_paid.exists():
        with transaction.atomic():
            deleted_count2 = empty_payments_with_paid.delete()[0]
            total_deleted += deleted_count2

    return {"status": "success", "deleted": total_deleted}


@shared_task(bind=True, max_retries=3)
def sync_attendance_payment_data1(
    self, company_id: Optional[int] = None
) -> Dict:
    """
    Оптимизированная версия синхронизации.
    Запускает все задачи параллельно через group().
    """
    from celery import group

    # Если указана компания - обрабатываем только её
    if company_id:
        companies = [company_id]
    else:
        # Получаем все компании
        companies = list(
            Custumer.objects.values_list("company_id", flat=True).distinct()
        )

    # Создаем группу задач для каждой компании
    tasks = []
    for cid in companies:
        tasks.extend(
            [
                fix_attendance_blocks.s(cid),
                recalculate_subscription_remained.s(cid),
                update_subscription_statuses.s(cid),
                create_missing_payment_records.s(cid),
                cleanup_empty_payments.s(cid),
            ]
        )

    # ✅ Запускаем ВСЕ задачи ПАРАЛЛЕЛЬНО
    # Celery распределит их между воркерами (concurrency=10)
    job = group(*tasks)
    result = job.apply_async()

    return {
        "status": "started",
        "tasks_count": len(tasks),
        "job_id": result.id,
        "message": "All tasks started in parallel",
    }
