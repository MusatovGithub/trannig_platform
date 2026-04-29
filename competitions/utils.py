"""
Утилиты для работы с соревнованиями и разрядами.
Оптимизированы для производительности и избежания N+1 запросов.
"""

from django.db import transaction
from django.db.models import F

from base.cache_utils import get_cached_sport_categories
from competitions.models import CustumerCompetitionResult
from custumer.models import Custumer


def get_customer_with_rank_info(customer_id, company):
    """
    Получает клиента с информацией о разряде в одном запросе.

    Args:
        customer_id: ID клиента
        company: Компания для проверки доступа

    Returns:
        Custumer: Клиент с предзагруженными данными
    """
    return (
        Custumer.objects.select_related("sport_category", "user")
        .filter(id=customer_id, company=company)
        .first()
    )


def get_sport_categories_ordered():
    """
    Получает все разряды, отсортированные по уровню из кеша.

    Returns:
        List: Разряды, отсортированные по уровню
    """
    return get_cached_sport_categories()


def can_assign_rank(customer, new_rank):
    """
    Проверяет, можно ли присвоить новый разряд клиенту.

    Args:
        customer: Объект клиента
        new_rank: Новый разряд для присвоения

    Returns:
        tuple: (можно_присвоить, причина)
    """
    if not customer or not new_rank:
        return False, "Отсутствуют данные клиента или разряда"

    current_rank = customer.sport_category

    # Если у клиента нет разряда, можно присвоить любой
    if not current_rank:
        return True, "У клиента нет разряда"

    # Если новый разряд выше текущего, можно присвоить
    if new_rank.level > current_rank.level:
        return True, (
            f"Новый разряд '{new_rank.name}' выше текущего "
            f"'{current_rank.name}'"
        )

    # Если разряды одинаковые, не меняем
    if new_rank.level == current_rank.level:
        return False, f"У клиента уже есть разряд '{current_rank.name}'"

    # Если новый разряд ниже текущего, не меняем
    return False, (
        f"Новый разряд '{new_rank.name}' ниже текущего '{current_rank.name}'"
    )


@transaction.atomic
def assign_rank_to_customer(customer, new_rank, result=None):
    """
    Присваивает разряд клиенту и обновляет результат соревнования.

    Args:
        customer: Объект клиента
        new_rank: Новый разряд
        result: Результат соревнования (может быть None при создании)

    Returns:
        tuple: (успех, сообщение, присвоен_клиенту)
    """
    try:
        # Проверяем, можно ли присвоить разряд клиенту
        can_assign, reason = can_assign_rank(customer, new_rank)

        # Присваиваем разряд клиенту только если можно
        if can_assign:
            customer.sport_category = new_rank
            customer.save(update_fields=["sport_category"])
            customer_updated = True
            message = f"Разряд '{new_rank.name}' успешно присвоен клиенту"
        else:
            customer_updated = False
            message = (
                f"Разряд '{new_rank.name}' сохранен в результате, "
                f"но клиенту не присвоен: {reason}"
            )

        # Обновляем результат соревнования, если он существует
        if result:
            result.sport_category = new_rank
            result.save(update_fields=["sport_category"])

        return True, message, customer_updated

    except Exception as e:
        return False, f"Ошибка при присвоении разряда: {str(e)}", False


def get_competition_results_with_ranks(competition_id, customer_id):
    """
    Получает результаты соревнования с информацией о разрядах в одном запросе.

    Args:
        competition_id: ID соревнования
        customer_id: ID клиента

    Returns:
        QuerySet: Результаты с предзагруженными данными
    """
    return (
        CustumerCompetitionResult.objects.select_related(
            "sport_category", "competition"
        )
        .filter(competition_id=competition_id, customer_id=customer_id)
        .order_by(
            "is_disqualified",
            F("place").asc(nulls_last=True),
            "distance",
            "style",
        )
    )


def bulk_update_customer_ranks(customer_rank_updates):
    """
    Массовое обновление разрядов клиентов для оптимизации.

    Args:
        customer_rank_updates: Список кортежей (customer_id, new_rank_id)

    Returns:
        int: Количество обновленных записей
    """
    if not customer_rank_updates:
        return 0

    # Группируем обновления по разрядам для оптимизации
    rank_groups = {}
    for customer_id, rank_id in customer_rank_updates:
        if rank_id not in rank_groups:
            rank_groups[rank_id] = []
        rank_groups[rank_id].append(customer_id)

    updated_count = 0

    # Обновляем разряды группами
    for rank_id, customer_ids in rank_groups.items():
        count = Custumer.objects.filter(id__in=customer_ids).update(
            sport_category_id=rank_id
        )
        updated_count += count

    return updated_count
