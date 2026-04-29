"""
Сервисы для работы с группами.
"""

from django.db import transaction

from groups_custumer.models import GroupsClass


def get_groups_by_customer(customer_id):
    """Получить все группы для клиента."""
    groups = GroupsClass.objects.filter(custumer=customer_id)
    return groups


@transaction.atomic
def create_group(name, sport_type, start_date, end_date, company, owner):
    """
    Создание группы с валидацией.

    Args:
        name: Название группы
        sport_type: Объект TypeSportsCompany
        start_date: Дата начала обучения (date)
        company: Компания
        owner: Пользователь-владелец

    Returns:
        GroupsClass: Созданная группа
    """
    group = GroupsClass.objects.create(
        name=name,
        type_sport=sport_type,
        strat_training=start_date,
        end_training=end_date,
        company=company,
        owner_id=owner,
    )
    return group


@transaction.atomic
def update_group(group, name, sport_type, start_date, end_date):
    """
    Обновление основных полей группы.

    Args:
        group: Объект GroupsClass для обновления
        name: Новое название
        sport_type: Новый тип спорта
        start_date: Новая дата начала
        end_date: Новая дата окончания

    Returns:
        GroupsClass: Обновленная группа
    """
    group.name = name
    group.type_sport = sport_type
    group.strat_training = start_date
    group.end_training = end_date
    group.save()
    return group


def assign_coaches(group, coaches):
    """
    Назначение тренеров группе.

    Args:
        group: Объект GroupsClass
        coaches: Список объектов Employe

    Returns:
        GroupsClass: Группа с назначенными тренерами
    """
    # Для создания используем add
    if not group.employe_id.exists():
        group.employe_id.add(*coaches)
    else:
        # Для обновления используем set
        group.employe_id.set(coaches)
    return group
