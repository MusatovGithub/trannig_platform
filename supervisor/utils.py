from datetime import timedelta

from django.utils import timezone

from custumer.models import ATTENDANCE_SCORE
from groups_custumer.models import ClasessProgramm, GroupClassessCustumer


def get_client_distances(custumer, today=None):
    """Функция для подсчета дистанции клиента."""
    if today is None:
        today = timezone.now().date()

    week_ago = today - timedelta(days=7)
    year_ago = today - timedelta(days=365)

    grade_statuses = list(ATTENDANCE_SCORE.keys())

    # Получаем все занятия за год одним запросом
    all_attendances = (
        GroupClassessCustumer.objects.filter(
            custumer=custumer,
            date__gte=year_ago,
            date__lte=today,
            attendance_status__in=grade_statuses,
        )
        .values("gr_class_id", "date")
        .distinct()
    )

    # Получаем все программы одним запросом
    gr_class_ids = [a["gr_class_id"] for a in all_attendances]
    programs = ClasessProgramm.objects.filter(
        classes_id__in=gr_class_ids
    ).values("classes_id", "distance")

    # Создаем словарь с суммированными дистанциями
    program_distances_dict = {}
    for program in programs:
        classes_id = program["classes_id"]
        try:
            distance = float(program["distance"]) if program["distance"] else 0
        except (ValueError, TypeError):
            distance = 0

        if classes_id in program_distances_dict:
            program_distances_dict[classes_id] += distance
        else:
            program_distances_dict[classes_id] = distance

    # Подсчитываем дистанции
    week_total = 0
    year_total = 0

    for attendance in all_attendances:
        distance = program_distances_dict.get(attendance["gr_class_id"], 0)
        if attendance["date"] >= week_ago:
            week_total += distance
        year_total += distance

    return round(week_total / 1000, 2), round(year_total / 1000, 2)
