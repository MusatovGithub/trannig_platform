def get_user_permissions(user):
    """Получает список прав пользователя из роли сотрудника с кешированием в Redis."""
    if not user.is_authenticated:
        return []

    # Кешируем права в атрибуте пользователя для избежания повторных запросов
    if hasattr(user, "_cached_permissions"):
        return user._cached_permissions

    # Проверяем кеш в Redis
    from django.core.cache import cache

    from base.cache_utils import CACHE_TIMEOUTS

    cache_key = f"user:{user.id}:permissions"
    cached_permissions = cache.get(cache_key)
    if cached_permissions is not None:
        user._cached_permissions = cached_permissions
        return cached_permissions

    try:
        permissions = []
        # Оптимизированный запрос с предзагрузкой связанных данных
        user_roles = user.user_id.select_related("roll").prefetch_related(
            "roll__perm"
        )
        for item in user_roles:
            if item.roll:
                permissions.extend(
                    [perm.name for perm in item.roll.perm.all()]
                )

        # Кешируем результат в памяти и Redis
        user._cached_permissions = permissions
        cache.set(cache_key, permissions, CACHE_TIMEOUTS["user_permissions"])
        return permissions
    except Exception:
        user._cached_permissions = []
        cache.set(cache_key, [], CACHE_TIMEOUTS["user_permissions"])
        return []


def has_permission(user, permission_name):
    """Проверяет, есть ли у пользователя определенное право."""
    if not user.is_authenticated:
        return False

    # Админы имеют все права
    if user.groups.filter(name="admin").exists():
        return True

    # Проверяем права ассистента
    if user.groups.filter(name="assistant").exists():
        user_permissions = get_user_permissions(user)
        return permission_name in user_permissions

    return False


def has_any_permission(user, permission_names):
    """Проверяет, есть ли у пользователя хотя бы одно из перечисленных прав."""
    if not user.is_authenticated:
        return False

    # Админы имеют все права
    if user.groups.filter(name="admin").exists():
        return True

    # Проверяем права ассистента
    if user.groups.filter(name="assistant").exists():
        user_permissions = get_user_permissions(user)
        return any(perm in user_permissions for perm in permission_names)

    return False


# Функции для проверки конкретных прав
def can_view_training_program(user):
    """Проверяет право на просмотр программы тренировки."""
    return has_permission(user, "Может просматривать программу тренировки")


def can_create_training_program(user):
    """Проверяет право на создание программы тренировки."""
    return has_permission(user, "Может создавать программу тренировки")


def can_edit_training_program(user):
    """Проверяет право на редактирование программы тренировки."""
    return has_permission(user, "Может редактировать программу тренировки")


def can_view_competitions(user):
    """Проверяет право на просмотр соревнований."""
    return has_permission(user, "Может просматривать соревнования")


def can_create_competitions(user):
    """Проверяет право на создание соревнований."""
    return has_permission(user, "Может создавать соревнования")


def can_edit_competitions(user):
    """Проверяет право на редактирование соревнований."""
    return has_permission(user, "Может редактировать соревнования")


def can_manage_competition_results(user):
    """Проверяет право на управление результатами соревнований."""
    return has_permission(user, "Может управлять результатами соревнований")


def can_add_attendance(user):
    """Проверяет право на добавление отметок посещаемости."""
    return has_permission(user, "Может добавлять отметки посещаемости")


def can_view_group_classes(user):
    """Проверяет право на просмотр занятий групп."""
    return has_permission(
        user, "Может просматривать занятия только своих групп"
    )


def can_view_own_groups(user):
    """Проверяет право на просмотр своих групп."""
    return has_permission(user, "Может просматривать только свои группы")


def can_view_own_customers(user):
    """Проверяет право на просмотр своих клиентов."""
    return has_permission(user, "Может просматривать только своих клиентов")
