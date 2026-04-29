from django.db import models
from django.utils import timezone

from authen.models import CustomUser
from custumer.models import SportCategory


class Product(models.Model):
    """Модель продуктов."""

    name = models.CharField(
        max_length=250, verbose_name="Название продукта", unique=True
    )
    description = models.TextField(
        verbose_name="Описание продукта",
        blank=True,
        null=True,
    )
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    price = models.IntegerField(verbose_name="Цена продукта")
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    sport_category = models.ForeignKey(
        SportCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ограничение по разряду",
        help_text=(
            "Если указан разряд, товар могут купить только клиенты с этим "
            "разрядом или выше"
        ),
    )

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"

    def __str__(self):
        """Возвращает название продукта."""
        return self.name

    def is_available_for_customer(self, customer):
        """
        Проверяет, может ли клиент купить этот товар.
        Возвращает True, если товар доступен для покупки.
        """
        if not self.sport_category:
            return True  # Товар доступен всем

        if not customer.sport_category:
            return False  # У клиента нет разряда

        # Клиент может купить товар, если его разряд >= требуемого
        return customer.sport_category.level >= self.sport_category.level


class Cart(models.Model):
    """Модель корзины."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

    def __str__(self):
        """Возвращает название корзины."""
        return f"{self.owner} - {self.product}"


class Order(models.Model):
    """Модель заказов."""

    STATUS_CHOICES = [
        ("PENDING", "Ожидает подтверждения"),
        ("CONFIRMED", "Подтвержден"),
        ("PROCESSING", "В обработке"),
        ("COMPLETED", "Выполнен"),
        ("CANCELLED", "Отменен"),
    ]

    customer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Клиент",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        verbose_name="Статус заказа",
    )
    total_amount = models.IntegerField(
        default=0, verbose_name="Общая сумма (баллы)"
    )
    created_at = models.DateTimeField(
        default=timezone.now, verbose_name="Дата создания"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Дата обновления"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Заказ #{self.id} - {self.customer} ({self.get_status_display()})"
        )

    def get_status_color(self):
        """Возвращает цвет для статуса."""
        colors = {
            "PENDING": "warning",
            "CONFIRMED": "info",
            "PROCESSING": "primary",
            "COMPLETED": "success",
            "CANCELLED": "danger",
        }
        return colors.get(self.status, "secondary")


class OrderItem(models.Model):
    """Модель позиций заказа."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заказ",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField(
        default=1, verbose_name="Количество"
    )
    price = models.IntegerField(verbose_name="Цена за единицу (баллы)")

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"
        unique_together = ["order", "product"]

    def __str__(self):
        return (
            f"{self.product.name} x{self.quantity} в заказе #{self.order.id}"
        )

    @property
    def total_price(self):
        """Общая стоимость позиции."""
        return self.price * self.quantity


class Purchase(models.Model):
    """Модель покупок (историческая запись)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Связанный заказ",
    )
    purchased_at = models.DateTimeField(
        default=timezone.now, verbose_name="Дата покупки"
    )

    class Meta:
        verbose_name = "Покупка"
        verbose_name_plural = "Покупки"
        unique_together = ["product", "owner", "order"]

    def __str__(self):
        """Возвращает название покупки."""
        return f"{self.owner} - {self.product}"
