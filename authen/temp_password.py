from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

TEMP_PASSWORD_TTL_SECONDS = settings.TEMP_PASSWORD_TTL_SECONDS or 8 * 60 * 60


def _temp_password_cache_key(user_id: int) -> str:
    return f"auth:temp_password:{user_id}"


def mark_temporary_password(user_id: int) -> None:
    cache.set(
        _temp_password_cache_key(user_id),
        "active",
        timeout=TEMP_PASSWORD_TTL_SECONDS,
    )


def has_temporary_password(user_id: int) -> bool:
    return bool(cache.get(_temp_password_cache_key(user_id)))


def clear_temporary_password(user_id: int) -> None:
    cache.delete(_temp_password_cache_key(user_id))


def set_temporary_password_state(user) -> None:
    user.must_change_password = True
    user.temporary_password_expires_at = timezone.now() + timedelta(
        seconds=TEMP_PASSWORD_TTL_SECONDS
    )
    user.save(
        update_fields=[
            "must_change_password",
            "temporary_password_expires_at",
        ]
    )
    mark_temporary_password(user.id)


def is_temporary_password_expired(user) -> bool:
    expires_at = user.temporary_password_expires_at
    if not expires_at:
        return True
    return timezone.now() >= expires_at


def clear_temporary_password_state(user) -> None:
    user.must_change_password = False
    user.temporary_password_expires_at = None
    user.save(
        update_fields=[
            "must_change_password",
            "temporary_password_expires_at",
        ]
    )
    clear_temporary_password(user.id)
