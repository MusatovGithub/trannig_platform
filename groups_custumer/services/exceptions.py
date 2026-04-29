"""
Кастомные исключения для бизнес-логики работы с группами.
"""


class GroupValidationError(Exception):
    """Ошибка валидации данных группы."""

    pass


class ScheduleValidationError(Exception):
    """Ошибка валидации данных расписания."""

    pass


class GroupPermissionError(Exception):
    """Ошибка прав доступа при работе с группами."""

    pass


class DateParseError(Exception):
    """Ошибка парсинга даты."""

    pass
