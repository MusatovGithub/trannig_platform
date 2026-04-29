"""
Утилиты для модуля custumer.
"""


def get_user_permissions(user):
    """
    Получает все разрешения пользователя одним оптимизированным запросом.

    Args:
        user: Пользователь Django

    Returns:
        dict: Словарь с разрешениями пользователя
    """
    if user.groups.filter(name="admin").exists():
        return {
            "can_add_subscriptions": True,
            "can_edit_subscriptions": True,
            "can_delete_subscriptions": True,
            "can_add_payments": True,
            "can_delete_payments": True,
            "can_add_cashiers": True,
            "can_edit_cashiers": True,
            "can_delete_cashiers": True,
            "can_view_cashiers": True,
            "can_add_templates": True,
            "can_edit_templates": True,
            "can_delete_templates": True,
            "can_add_customers": True,
            "can_edit_customers": True,
            "can_delete_customers": True,
            "can_view_customers": True,
            "can_view_own_customers": True,
        }

    # Получаем все разрешения пользователя одним запросом
    user_roles = (
        user.user_id.select_related("roll")
        .prefetch_related("roll__perm")
        .all()
    )
    all_permissions = [
        permission.name
        for role in user_roles
        for permission in role.roll.perm.all()
    ]

    return {
        "can_add_subscriptions": (
            "Может добавлять Абонементы" in all_permissions
        ),
        "can_edit_subscriptions": (
            "Может редактировать Абонементы" in all_permissions
        ),
        "can_delete_subscriptions": (
            "Может удалять Абонементы" in all_permissions
        ),
        "can_add_payments": (
            "Может создавать статьи доходов" in all_permissions
        ),
        "can_delete_payments": ("Может удалять платежи" in all_permissions),
        "can_add_cashiers": ("Может добавлять кассы" in all_permissions),
        "can_edit_cashiers": ("Может редактировать кассы" in all_permissions),
        "can_delete_cashiers": ("Может удалять кассы" in all_permissions),
        "can_view_cashiers": ("Может просматривать кассы" in all_permissions),
        "can_add_templates": ("Может добавлять шаблоны" in all_permissions),
        "can_edit_templates": (
            "Может редактировать шаблоны" in all_permissions
        ),
        "can_delete_templates": ("Может удалять шаблоны" in all_permissions),
        "can_add_customers": ("Может добавлять клиентов" in all_permissions),
        "can_edit_customers": (
            "Может редактировать клиентов" in all_permissions
        ),
        "can_delete_customers": ("Может удалять клиентов" in all_permissions),
        "can_view_customers": (
            "Может просматривать клиентов" in all_permissions
        ),
        "can_view_own_customers": (
            "Может просматривать клиентов только в своих группах"
            in all_permissions
        ),
    }
