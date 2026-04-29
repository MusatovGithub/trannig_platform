"""
Валидаторы для данных групп и расписаний.
"""

from datetime import datetime

from authen.models import TypeSportsCompany
from employe.models import Employe

from .exceptions import (
    DateParseError,
    GroupValidationError,
    ScheduleValidationError,
)


def parse_date_field(date_str, field_name="дата"):
    """
    Безопасный парсинг даты с поддержкой нескольких форматов.

    Args:
        date_str: Строка с датой
        field_name: Название поля для сообщения об ошибке

    Returns:
        date: Объект даты

    Raises:
        DateParseError: Если дата не может быть распознана
    """
    if not date_str:
        raise DateParseError(f"Поле '{field_name}' обязательно для заполнения")

    # Поддерживаемые форматы дат
    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    raise DateParseError(
        f"Неверный формат даты в поле '{field_name}'. "
        f"Ожидается формат: ДД.ММ.ГГГГ (например, 01.12.2025)"
    )


def validate_end_date(end_date_str, start_date):
    """
    Валидация и парсинг конечной даты обучения.

    ИСПРАВЛЕНИЕ БАГА: правильная обработка end_date из POST.
    Если передано число дней, конвертируем в дату.
    Если передана строка с датой, парсим её.

    Args:
        end_date_str: Строка с конечной датой или количеством дней
        start_date: Дата начала обучения (объект date)

    Returns:
        date или None: Конечная дата обучения или None (по умолчанию +2 года)
    """
    if not end_date_str:
        return None

    # Попытка распарсить как дату
    try:
        return parse_date_field(end_date_str, "конечная дата")
    except DateParseError:
        pass

    # Попытка интерпретировать как число дней
    try:
        days = int(end_date_str)
        if days <= 0:
            raise ScheduleValidationError(
                "Количество дней должно быть положительным числом"
            )
        from datetime import timedelta

        return start_date + timedelta(days=days)
    except ValueError:
        raise ScheduleValidationError(
            f"Неверный формат конечной даты: '{end_date_str}'. "
            f"Ожидается дата (ДД.ММ.ГГГГ) или количество дней (число)"
        )


def validate_group_data(
    name, sport_type_id, coaches_ids, start_date_str, company
):
    """
    Валидация основных полей группы.

    Args:
        name: Название группы
        sport_type_id: ID типа спорта
        coaches_ids: Список ID тренеров
        start_date_str: Строка с датой начала
        company: Компания пользователя

    Returns:
        tuple: (name, sport_type, coaches, start_date)

    Raises:
        GroupValidationError: При ошибке валидации
    """
    # Проверка обязательных полей
    if not name or not name.strip():
        raise GroupValidationError(
            "Название группы обязательно для заполнения"
        )

    if not sport_type_id:
        raise GroupValidationError("Вид спорта обязателен для заполнения")

    if not coaches_ids or len(coaches_ids) == 0:
        raise GroupValidationError(
            "Необходимо выбрать хотя бы одного тренера для группы"
        )

    if not start_date_str:
        raise GroupValidationError(
            "Дата начала обучения обязательна для заполнения"
        )

    # Парсинг даты
    try:
        start_date = parse_date_field(start_date_str, "дата начала обучения")
    except DateParseError as e:
        raise GroupValidationError(str(e))

    # Проверка существования типа спорта
    try:
        sport_type = TypeSportsCompany.objects.get(
            id=sport_type_id, company=company
        )
    except TypeSportsCompany.DoesNotExist:
        raise GroupValidationError(
            f"Указанный вид спорта (ID: {sport_type_id}) не существует"
        )

    # Проверка существования тренеров
    coaches = Employe.objects.filter(id__in=coaches_ids, company=company)
    if coaches.count() != len(coaches_ids):
        raise GroupValidationError(
            "Один или несколько выбранных тренеров не найдены"
        )

    return name.strip(), sport_type, list(coaches), start_date


def validate_schedule_data(name_schedule, weeks_data, time_start, time_end):
    """
    Валидация данных расписания.

    Args:
        name_schedule: Список названий занятий
        weeks_data: Список ID дней недели
        time_start: Список времени начала
        time_end: Список времени окончания

    Returns:
        list: Список валидных записей расписания (name, week_id, start, end)

    Raises:
        ScheduleValidationError: При ошибке валидации
    """
    if not weeks_data or len(weeks_data) == 0:
        # Расписание необязательно, можно создать группу без него
        return []

    # Проверка, что все списки одинаковой длины
    lengths = [
        len(name_schedule),
        len(weeks_data),
        len(time_start),
        len(time_end),
    ]
    if len(set(lengths)) > 1:
        raise ScheduleValidationError(
            "Несоответствие количества элементов в данных расписания"
        )

    validated_schedules = []

    for name, week_id, start, end in zip(
        name_schedule, weeks_data, time_start, time_end
    ):
        # Пропускаем пустые записи
        if not week_id or not start or not end:
            continue

        # Валидация week_id
        try:
            week_id_int = int(week_id)
        except (ValueError, TypeError):
            raise ScheduleValidationError(f"Неверный ID дня недели: {week_id}")

        # Валидация времени
        try:
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
        except ValueError:
            raise ScheduleValidationError(
                "Неверный формат времени. Ожидается ЧЧ:ММ (например, 10:00)"
            )

        # Проверка логики времени
        if start_time >= end_time:
            raise ScheduleValidationError(
                f"Время начала ({start}) должно быть раньше времени окончания ({end})"  # noqa: E501
            )

        validated_schedules.append(
            {
                "name": name.strip() if name else "",
                "week_id": week_id_int,
                "start_time": start,
                "end_time": end,
            }
        )

    return validated_schedules
