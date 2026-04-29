from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from base.permissions import admin_or_assistant_required, admin_required
from custumer.models import SportCategory
from market.models import Order, OrderItem, Product, Purchase


@admin_or_assistant_required
def get_product_list(request):
    """Вывод списка продуктов."""
    search = request.GET.get("search", "")
    if search:
        products = Product.objects.filter(
            name__contains=search, owner=request.user
        ).select_related("sport_category")
    else:
        products = Product.objects.filter(owner=request.user).select_related(
            "sport_category"
        )
    products = products.order_by("-id")
    paginator = Paginator(products, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request, "market/index.html", {"page_obj": page_obj, "search": search}
    )


@admin_required
def create_product(request):
    """Создание продукта."""
    if request.method == "POST":
        name = request.POST.get("name")
        price = request.POST.get("price")
        description = request.POST.get("description")
        image = request.FILES.get("image")
        sport_category_id = request.POST.get("sport_category")
        sport_category = None
        if sport_category_id:
            try:
                sport_category = SportCategory.objects.get(
                    id=sport_category_id
                )
            except SportCategory.DoesNotExist:
                pass
        Product.objects.create(
            name=name,
            price=price,
            owner=request.user,
            image=image,
            description=description,
            sport_category=sport_category,
        )
        return redirect("market:get_product_list")

    sport_categories = SportCategory.objects.all().order_by("level")
    return render(
        request, "market/create.html", {"sport_categories": sport_categories}
    )


@admin_required
def update_product(request, pk):
    """Обновление продукта."""
    product = Product.objects.get(id=pk)
    if request.method == "POST":
        name = request.POST.get("name")
        price = request.POST.get("price")
        description = request.POST.get("description")
        image = request.FILES.get("image")
        sport_category_id = request.POST.get("sport_category")
        sport_category = None
        if sport_category_id:
            try:
                sport_category = SportCategory.objects.get(
                    id=sport_category_id
                )
            except SportCategory.DoesNotExist:
                pass
        product.name = name
        product.price = price
        product.description = description
        if image:
            product.image = image
        product.sport_category = sport_category
        product.save()
        return redirect("market:get_product_list")

    sport_categories = SportCategory.objects.all().order_by("level")
    return render(
        request,
        "market/update.html",
        {"product": product, "sport_categories": sport_categories},
    )


@admin_required
def delete_product(request, pk):
    """Удаление продукта."""
    product = Product.objects.get(id=pk)
    product.delete()
    return redirect("market:get_product_list")


@admin_or_assistant_required
def order_list(request):
    """Список заказов."""
    status_filter = request.GET.get("status", "")
    search = request.GET.get("search", "")

    orders = (
        Order.objects.all()
        .select_related("customer")
        .prefetch_related("items__product")
    )

    if status_filter:
        orders = orders.filter(status=status_filter)

    if search:
        orders = orders.filter(
            customer__username__icontains=search
        ) | orders.filter(id__icontains=search)

    orders = orders.order_by("-created_at")

    paginator = Paginator(orders, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "search": search,
        "status_choices": Order.STATUS_CHOICES,
    }

    return render(request, "market/orders.html", context)


@admin_or_assistant_required
def order_detail(request, pk):
    """Детали заказа."""
    order = get_object_or_404(Order, pk=pk)
    return render(request, "market/order_detail.html", {"order": order})


@admin_required
def update_order_status(request, pk):
    """Обновление статуса заказа."""
    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        new_status = request.POST.get("status")
        notes = request.POST.get("notes", "")

        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            if notes:
                order.notes = notes
            order.save()

            messages.success(
                request,
                f'Статус заказа #{order.id} обновлен на "{order.get_status_display()}"',  # noqa: E501
            )

            # Если заказ завершен, создаем записи о покупках (если их еще нет)
            if new_status == "COMPLETED":
                with transaction.atomic():
                    purchases_created = 0
                    for item in order.items.all():
                        # Проверяем, есть ли уже запись
                        # о покупке для этого товара в этом заказе
                        purchase, created = Purchase.objects.get_or_create(
                            product=item.product,
                            owner=order.customer,
                            order=order,
                            defaults={"purchased_at": timezone.now()},
                        )
                        if created:
                            purchases_created += 1

                    if purchases_created > 0:
                        messages.info(
                            request,
                            f"Заказ завершен. Создано {purchases_created} записей о покупках.",  # noqa: E501
                        )
                    else:
                        messages.info(
                            request,
                            "Заказ завершен. Записи о покупках уже существуют.",  # noqa: E501
                        )

        return redirect("market:order_detail", pk=order.id)

    return render(
        request,
        "market/update_order_status.html",
        {"order": order, "status_choices": Order.STATUS_CHOICES},
    )


@admin_or_assistant_required
def sales_report(request):
    """Отчет по продажам."""
    # Параметры фильтрации
    days = int(request.GET.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    # Статистика по заказам
    orders_stats = Order.objects.filter(
        created_at__gte=start_date, status="COMPLETED"
    ).aggregate(total_orders=Count("id"), total_amount=Sum("total_amount"))

    # Топ товаров
    top_products = (
        OrderItem.objects.filter(
            order__created_at__gte=start_date, order__status="COMPLETED"
        )
        .values("product__name")
        .annotate(total_sold=Sum("quantity"), total_revenue=Sum("price"))
        .order_by("-total_sold")[:10]
    )

    # Статистика по статусам
    status_stats = (
        Order.objects.filter(created_at__gte=start_date)
        .values("status")
        .annotate(count=Count("id"))
    )

    context = {
        "orders_stats": orders_stats,
        "top_products": top_products,
        "status_stats": status_stats,
        "days": days,
        "start_date": start_date,
    }

    return render(request, "market/sales_report.html", context)
