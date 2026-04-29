from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def get_employee_permissions(context):
    """Получает все права сотрудника для оптимизации"""
    user = context["request"].user
    if not user.is_authenticated:
        return {}

    # Админы имеют все права
    if user.groups.filter(name="admin").exists():
        return {
            "can_view_groups": True,
            "can_view_classes": True,
            "can_view_competitions": True,
            "can_view_training": True,
            "can_view_customers": True,
            "can_view_employees": True,
        }

    # Для ассистентов получаем права один раз
    if user.groups.filter(name="assistant").exists():
        from employe.utils import get_user_permissions

        # Получаем все права пользователя одним запросом
        user_permissions = get_user_permissions(user)

        return {
            "can_view_groups": any(
                perm in user_permissions
                for perm in [
                    "Может просматривать группы",
                    "Может просматривать только свои группы",
                ]
            ),
            "can_view_classes": (
                "Может просматривать занятия только своих групп"
                in user_permissions
            ),
            "can_view_competitions": any(
                perm in user_permissions
                for perm in [
                    "Может просматривать соревнования",
                    "Может создавать соревнования",
                    "Может редактировать соревнования",
                    "Может управлять результатами соревнований",
                ]
            ),
            "can_view_training": any(
                perm in user_permissions
                for perm in [
                    "Может просматривать программу тренировки",
                    "Может создавать программу тренировки",
                    "Может редактировать программу тренировки",
                ]
            ),
            "can_view_customers": any(
                perm in user_permissions
                for perm in [
                    "Может просматривать клиентов",
                    "Может просматривать только своих клиентов",
                ]
            ),
            "can_view_employees": (
                "Может просматривать сотрудников" in user_permissions
            ),
        }

    return {}


@register.filter
def has_employee_permission(user_permissions, permission_key):
    """Проверяет наличие права у сотрудника"""
    return user_permissions.get(permission_key, False)
