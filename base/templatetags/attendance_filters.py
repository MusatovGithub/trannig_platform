from django import template

register = template.Library()

ATTENDANCE_SCORE = {
    "attended_2": 2,
    "attended_3": 3,
    "attended_4": 4,
    "attended_5": 5,
    "attended_10": 10,
}


@register.filter
def attendance_score_display(value):
    return ATTENDANCE_SCORE.get(value, "")
