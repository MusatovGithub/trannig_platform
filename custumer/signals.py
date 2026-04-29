from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from authen.models import CustomUser
from custumer.models import (
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from groups_custumer.models import GroupClassessCustumer


@receiver(post_save, sender=CustomUser)
def sync_customuser_to_custumer(sender, instance, created, **kwargs):
    """Автоматически синхронизирует данные из CustomUser в связанный Custumer."""  # noqa: E501
    if not created:  # Только при обновлении, не при создании
        try:
            # Ищем связанный профиль клиента
            custumer = Custumer.objects.get(user=instance)

            # Синхронизируем основные поля
            if instance.first_name:
                custumer.full_name = instance.first_name

            if instance.email:
                custumer.email = instance.email

            if instance.phone:
                custumer.phone = instance.phone

            # Синхронизируем аватар в фото (если есть)
            if instance.avatar:
                custumer.photo = instance.avatar

            # Сохраняем изменения
            custumer.save(
                update_fields=["full_name", "email", "phone", "photo"]
            )

        except Custumer.DoesNotExist:
            # Если профиль клиента не существует, ничего не делаем
            pass


@receiver(post_save, sender=Custumer)
def sync_custumer_to_customuser(sender, instance, created, **kwargs):
    """Автоматически синхронизирует данные из Custumer в связанный CustomUser."""  # noqa: E501
    if (
        not created and instance.user
    ):  # Только при обновлении и если есть связь
        try:
            user = instance.user

            # Синхронизируем основные поля
            if instance.full_name:
                user.first_name = instance.full_name
                user.username = instance.email or user.username

            if instance.email:
                user.email = instance.email
                user.username = instance.email

            if instance.phone:
                user.phone = instance.phone

            # Синхронизируем фото в аватар (если есть)
            if instance.photo:
                user.avatar = instance.photo

            # Сохраняем изменения
            user.save(
                update_fields=[
                    "first_name",
                    "email",
                    "username",
                    "phone",
                    "avatar",
                ]
            )

        except Exception:
            # Если произошла ошибка, ничего не делаем
            pass


@receiver([post_save, post_delete], sender=CustumerSubscriptonPayment)
def update_subscription_status(sender, instance, **kwargs):
    """
    Автоматически обновляет статус абонемента при изменении платежей.
    """
    try:
        # ВАЖНО: Проверяем существование абонемента
        # При каскадном удалении абонемента instance.subscription
        # может не существовать
        if not instance.subscription_id:
            return

        subscription = CustumerSubscription.objects.filter(
            id=instance.subscription_id
        ).first()

        if not subscription or subscription.is_free:
            return

        # Получаем общую сумму всех платежей по этому абонементу
        total_paid = sum(
            payment.summ
            for payment in subscription.payments.all()
            if payment.summ is not None
        )

        # Обновляем статус в зависимости от суммы платежей
        if subscription.total_cost and total_paid >= int(
            subscription.total_cost
        ):
            subscription.attendance_status = "paid"
        elif subscription.total_cost and total_paid < int(
            subscription.total_cost
        ):
            subscription.attendance_status = "unpaid"

        subscription.save(update_fields=["attendance_status"])
    except (
        CustumerSubscription.DoesNotExist,
        AttributeError,
        ValueError,
    ):
        # Если абонемент уже удален или возникла другая ошибка - игнорируем
        pass


@receiver(pre_delete, sender=CustumerSubscription)
def reset_attendances_before_subscription_delete(sender, instance, **kwargs):
    """
    КРИТИЧНО: При удалении абонемента сбрасываем is_block для всех
    связанных посещений, чтобы они не считались "оплаченными наличными".

    Этот сигнал срабатывает ПЕРЕД удалением абонемента, что позволяет
    корректно обработать связанные посещения.
    """
    # Получаем все посещения, связанные с удаляемым абонементом
    affected_attendances = GroupClassessCustumer.objects.filter(
        used_subscription=instance
    )

    # Сбрасываем is_block для всех связанных посещений
    # ПЕРЕД тем, как Django применит on_delete=SET_NULL
    affected_attendances.update(is_block=False)
