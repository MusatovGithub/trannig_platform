import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from authen.models import CustomUser
from employe.models import Employe

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def sync_customuser_to_employe(sender, instance, created, **kwargs):
    """Автоматически синхронизирует данные из CustomUser в связанный Employe."""  # noqa: E501
    try:
        employe = Employe.objects.get(user=instance)
        updated = False

        # Синхронизируем основные поля
        if instance.first_name and employe.full_name != instance.first_name:
            employe.full_name = instance.first_name
            updated = True

        if instance.phone and employe.phone != instance.phone:
            employe.phone = instance.phone
            updated = True

        # Сохраняем изменения только если что-то изменилось
        if updated:
            employe.save(update_fields=["full_name", "phone"])

    except Employe.DoesNotExist:
        # Если профиль сотрудника не существует, ничего не делаем
        pass
    except Exception as e:
        # Логируем ошибку, но не прерываем выполнение
        logger.error(f"Ошибка синхронизации CustomUser -> Employe: {e}")


@receiver(post_save, sender=Employe)
def sync_employe_to_customuser(sender, instance, created, **kwargs):
    """Автоматически синхронизирует данные из Employe в связанный CustomUser."""  # noqa: E501
    if instance.user:  # Если есть связь с пользователем
        try:
            user = instance.user
            updated = False

            if instance.full_name and user.first_name != instance.full_name:
                user.first_name = instance.full_name
                updated = True

            if instance.phone and user.phone != instance.phone:
                user.phone = instance.phone
                updated = True

            # Сохраняем изменения только если что-то изменилось
            if updated:
                user.save(update_fields=["first_name", "phone"])

        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            logger.error(f"Ошибка синхронизации Employe -> CustomUser: {e}")
