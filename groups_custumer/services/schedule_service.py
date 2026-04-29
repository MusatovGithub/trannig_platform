"""
Сервисы для работы с расписаниями и занятиями.
Оптимизированы через bulk_create для минимизации SQL-запросов.
"""

from datetime import timedelta

from django.db import transaction

from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    Schedule,
    Week,
)

# Перевод дней недели
WEEKDAY_TRANSLATION = {
    "Monday": "Понедельник",
    "Tuesday": "Вторник",
    "Wednesday": "Среда",
    "Thursday": "Четверг",
    "Friday": "Пятница",
    "Saturday": "Суббота",
    "Sunday": "Воскресенье",
}


@transaction.atomic
def create_schedules_bulk(group, validated_schedules):
    """
    Массовое создание расписаний через bulk_create.

    Args:
        group: Объект GroupsClass
        validated_schedules: Список валидных данных расписания

    Returns:
        list: Список созданных объектов Schedule
    """
    if not validated_schedules:
        return []

    schedule_objects = []
    for schedule_data in validated_schedules:
        schedule_objects.append(
            Schedule(
                groups_id=group,
                name=schedule_data["name"],
                week_id=schedule_data["week_id"],
                strat_time=schedule_data["start_time"],
                end_time=schedule_data["end_time"],
            )
        )

    # Один запрос вместо N запросов
    created_schedules = Schedule.objects.bulk_create(schedule_objects)
    return created_schedules


def generate_group_classes(
    group, validated_schedules, start_date, end_date, company, owner
):
    """
    Генерация списка занятий на основе расписания.

    Args:
        group: Объект GroupsClass
        validated_schedules: Список валидных данных расписания
        start_date: Дата начала (date)
        end_date: Дата окончания (date) или None (по умолчанию +2 года)
        company: Компания
        owner: Пользователь-владелец

    Returns:
        list: Список объектов GroupClasses (не сохраненных в БД)
    """
    if not validated_schedules:
        return []

    # Если конечная дата не указана, берем 2 года от начала
    if end_date is None:
        end_date = start_date + timedelta(days=730)  # 2 года

    classes_objects = []

    # Получаем первого тренера группы для занятий
    first_coach = group.employe_id.first()
    if not first_coach:
        # Если нет тренеров, пропускаем создание занятий
        return []

    # Загружаем все недели один раз
    week_ids = [s["week_id"] for s in validated_schedules]
    weeks = {w.id: w for w in Week.objects.filter(id__in=week_ids)}

    for schedule_data in validated_schedules:
        week_id = schedule_data["week_id"]
        week_obj = weeks.get(week_id)

        if not week_obj:
            continue

        current_date = start_date

        # Итерация по датам
        while current_date <= end_date:
            weekday_english = current_date.strftime("%A")
            weekday_russian = WEEKDAY_TRANSLATION.get(
                weekday_english, weekday_english
            )

            # Если день недели совпадает с расписанием
            if weekday_russian == week_obj.name:
                classes_objects.append(
                    GroupClasses(
                        groups_id=group,
                        date=current_date,
                        strat=schedule_data["start_time"],
                        end=schedule_data["end_time"],
                        name=schedule_data["name"],
                        employe=first_coach,
                        company=company,
                        owner=owner,
                        is_manual=False,
                    )
                )

            current_date += timedelta(days=1)

    return classes_objects


@transaction.atomic
def create_group_classes_bulk(classes_objects):
    """
    Массовое создание занятий через bulk_create.

    Args:
        classes_objects: Список объектов GroupClasses (не сохраненных)

    Returns:
        list: Список созданных объектов GroupClasses
    """
    if not classes_objects:
        return []

    # Один запрос вместо N запросов
    created_classes = GroupClasses.objects.bulk_create(classes_objects)
    return created_classes


@transaction.atomic
def create_attendance_records_bulk(group_classes, customers, company, owner):
    """
    Массовое создание записей посещаемости через bulk_create.

    Args:
        group_classes: Список объектов GroupClasses
        customers: QuerySet или список объектов Custumer
        company: Компания
        owner: Пользователь-владелец

    Returns:
        list: Список созданных объектов GroupClassessCustumer
    """
    if not group_classes or not customers:
        return []

    attendance_objects = []

    for group_class in group_classes:
        for customer in customers:
            attendance_objects.append(
                GroupClassessCustumer(
                    gr_class=group_class,
                    custumer=customer,
                    date=group_class.date,
                    attendance_status="none",
                    company=company,
                    owner=owner,
                )
            )

    # Один запрос вместо N × M запросов
    # ignore_conflicts пропустит дубликаты без ошибок
    created_attendance = GroupClassessCustumer.objects.bulk_create(
        attendance_objects, ignore_conflicts=True
    )
    return created_attendance


def preserve_attendance_data(group):
    """
    Сохранение существующих данных посещаемости при обновлении.

    Args:
        group: Объект GroupsClass

    Returns:
        dict: Словарь {(custumer_id, date): attendance_data}
    """
    old_attendances = GroupClassessCustumer.objects.filter(
        gr_class__groups_id=group
    ).select_related("used_subscription")

    attendance_map = {}
    for att in old_attendances:
        key = (att.custumer_id, att.date)
        attendance_map[key] = {
            "attendance_status": att.attendance_status,
            "used_subscription": att.used_subscription,
            "is_block": att.is_block,
            "is_none": att.is_none,
            "comment": att.comment,
        }

    return attendance_map


@transaction.atomic
def restore_attendance_data(
    group_classes, attendance_map, customers, company, owner
):
    """
    Восстановление данных посещаемости после обновления расписания.

    Args:
        group_classes: Список новых объектов GroupClasses
        attendance_map: Словарь с сохраненными данными посещаемости
        customers: QuerySet или список клиентов группы
        company: Компания
        owner: Пользователь-владелец

    Returns:
        list: Список созданных объектов GroupClassessCustumer
    """
    if not group_classes:
        return []

    customers_objects = []

    for group_class in group_classes:
        for customer in customers:
            key = (customer.id, group_class.date)

            # Если была старая запись — переносим её данные
            if key in attendance_map:
                att_data = attendance_map[key]
                customers_objects.append(
                    GroupClassessCustumer(
                        gr_class=group_class,
                        custumer=customer,
                        date=group_class.date,
                        attendance_status=att_data["attendance_status"],
                        used_subscription=att_data["used_subscription"],
                        is_block=att_data["is_block"],
                        is_none=att_data["is_none"],
                        comment=att_data.get("comment", ""),
                        company=company,
                        owner=owner,
                    )
                )
            else:
                # Новое посещение — статус по умолчанию
                customers_objects.append(
                    GroupClassessCustumer(
                        gr_class=group_class,
                        custumer=customer,
                        date=group_class.date,
                        attendance_status="none",
                        company=company,
                        owner=owner,
                    )
                )

    # Массовое создание с игнорированием конфликтов
    created_records = GroupClassessCustumer.objects.bulk_create(
        customers_objects, ignore_conflicts=True
    )
    return created_records


@transaction.atomic
def delete_old_schedule_and_classes(group):
    """
    Удаление старого расписания и занятий при обновлении.

    Args:
        group: Объект GroupsClass
    """
    # Удаляем старое расписание
    Schedule.objects.filter(groups_id=group).delete()

    # Удаляем только автоматически созданные занятия
    GroupClasses.objects.filter(groups_id=group, is_manual=False).delete()
