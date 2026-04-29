from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Case, IntegerField, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from competitions.models import CustumerCompetitionResult
from custumer.models import (
    ATTENDANCE_SCORE,
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
    PointsHistory,
)
from custumer.schemas import ReasonTextChoices
from groups_custumer.models import (
    ClasessProgramm,
    GroupClassessCustumer,
    GroupsClass,
)
from market.models import Cart, Order, OrderItem, Product, Purchase
from supervisor.views import is_client


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_client_diary(request):
    today = timezone.localdate()
    custumer = getattr(request.user, "client_profile", None)
    if not custumer:
        return render(request, "page_404.html")
    date_from = request.GET.get("date_from", today)
    date_to = request.GET.get("date_to", today + timedelta(days=30))
    group_id = request.GET.get("group_id")
    show_prev = request.GET.get("show_prev")
    groups = custumer.groups.all()
    diary_entries = GroupClassessCustumer.objects.filter(custumer=custumer)
    if group_id:
        diary_entries = diary_entries.filter(gr_class__groups_id__id=group_id)
    # По умолчанию показываем занятия начиная с сегодняшнего дня,
    # если явно не запрошены прошлые
    if not date_from and not show_prev:
        date_from = timezone.localdate()
    if date_from:
        diary_entries = diary_entries.filter(date__gte=date_from)
    if date_to:
        diary_entries = diary_entries.filter(date__lte=date_to)

    diary_entries = (
        diary_entries.select_related(
            "gr_class__groups_id", "gr_class__employe", "owner"
        )
        .prefetch_related("gr_class__classes")
        .order_by("date")
    )

    context = {
        "diary_entries": diary_entries,
        "date_from": date_from,
        "date_to": date_to,
        "groups": groups,
        "group_id": group_id,
        "show_prev": show_prev,
    }
    return render(request, "customer/cabinet/diary.html", context)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_my_competitions(request):
    user = request.user

    # Фильтры
    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    end_date = request.GET.get("end_date", "")
    location = request.GET.get("location", "")

    customer = Custumer.objects.get(user=user)

    # Оптимизация: получаем результаты с соревнованиями
    results_qs = CustumerCompetitionResult.objects.select_related(
        "competition", "customer", "sport_category"
    ).filter(customer_id=customer.id)
    if search:
        results_qs = results_qs.filter(competition__name__icontains=search)
    if date and end_date:
        try:
            date_obj = datetime.strptime(date, "%d.%m.%Y").date()
            end_date_obj = datetime.strptime(end_date, "%d.%m.%Y").date()
            results_qs = results_qs.filter(
                competition__date__gte=date_obj,
                competition__end_date__lte=end_date_obj,
            )
        except ValueError:
            pass
    elif date:
        try:
            date_obj = datetime.strptime(date, "%d.%m.%Y").date()
            results_qs = results_qs.filter(competition__date__gte=date_obj)
        except ValueError:
            pass
    elif end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%d.%m.%Y").date()
            results_qs = results_qs.filter(
                competition__end_date__lte=end_date_obj
            )
        except ValueError:
            pass
    if location:
        results_qs = results_qs.filter(
            competition__location__icontains=location
        )

    results_qs = results_qs.order_by("-competition__date", "competition__name")

    context = {
        "results": results_qs,
        "search": search,
        "date": date,
        "location": location,
    }
    return render(request, "customer/cabinet/my_competitions.html", context)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_marketplace(request):
    """Магазин."""
    search = request.GET.get("search", "")
    company = request.user.company
    company_users = company.company.all()
    if search:
        products = Product.objects.filter(
            name__contains=search, owner__in=company_users
        ).select_related("sport_category")
    else:
        products = Product.objects.filter(
            owner__in=company_users
        ).select_related("sport_category")
    products.order_by("-id")
    products = products.order_by("-id")
    paginator = Paginator(products, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "customer/cabinet/marketplace.html",
        {"page_obj": page_obj, "search": search},
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def buy_product(request, product_id):
    """Создание заказа на товар."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Неверный метод"}, status=405
        )

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Товар не найден"}, status=404
        )

    custumer = request.user.client_profile  # Получаем профиль клиента

    # Проверяем доступность товара для клиента по разряду
    if not product.is_available_for_customer(custumer):
        return JsonResponse(
            {
                "success": False,
                "error": "У вас недостаточный разряд для покупки этого товара",
            }
        )

    with transaction.atomic():
        # Блокируем строку клиента до конца транзакции
        custumer = Custumer.objects.select_for_update().get(pk=custumer.pk)
        if custumer.balance < product.price:
            return JsonResponse(
                {"success": False, "error": "Недостаточно баллов"}
            )

        # Создаем заказ
        order = Order.objects.create(
            customer=request.user, total_amount=product.price, status="PENDING"
        )

        # Добавляем товар в заказ
        OrderItem.objects.create(
            order=order, product=product, quantity=1, price=product.price
        )

        # Списываем баллы
        custumer.balance -= product.price
        custumer.save()

        # Создаем запись в истории баллов о списании
        PointsHistory.objects.create(
            custumer=custumer,
            points=-product.price,  # Отрицательное значение для списания
            reason=ReasonTextChoices.PURCHASE,
            description=f"Покупка товара: {product.name}",
            awarded_by=request.user,
        )

        # Записи о покупках будут созданы при завершении заказа

    return JsonResponse(
        {
            "success": True,
            "message": f"Заказ #{order.id} создан успешно! Ожидает подтверждения.",  # noqa: E501
            "order_id": order.id,
        }
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def add_to_cart(request, product_id):
    """Добавление товара в корзину."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Неверный метод"}, status=405
        )

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Товар не найден"}, status=404
        )

    custumer = request.user.client_profile

    # Проверяем доступность товара для клиента по разряду
    if not product.is_available_for_customer(custumer):
        return JsonResponse(
            {
                "success": False,
                "error": "У вас недостаточный разряд для покупки этого товара",
            }
        )

    # Проверяем, есть ли уже этот товар в корзине
    cart_item, created = Cart.objects.get_or_create(
        product=product, owner=request.user
    )

    if not created:
        return JsonResponse({"success": False, "error": "Товар уже в корзине"})

    return JsonResponse(
        {"success": True, "message": "Товар добавлен в корзину"}
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def remove_from_cart(request, product_id):
    """Удаление товара из корзины."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Неверный метод"}, status=405
        )

    try:
        cart_item = Cart.objects.get(product_id=product_id, owner=request.user)
        cart_item.delete()
        return JsonResponse(
            {"success": True, "message": "Товар удален из корзины"}
        )
    except Cart.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Товар не найден в корзине"},
            status=404,
        )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_cart(request):
    """Просмотр корзины."""
    cart_items = Cart.objects.filter(owner=request.user).select_related(
        "product"
    )
    total_amount = sum(item.product.price for item in cart_items)

    return render(
        request,
        "customer/cabinet/cart.html",
        {"cart_items": cart_items, "total_amount": total_amount},
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def checkout_cart(request):
    """Оформление заказа из корзины."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Неверный метод"}, status=405
        )

    cart_items = Cart.objects.filter(owner=request.user).select_related(
        "product"
    )

    if not cart_items.exists():
        return JsonResponse({"success": False, "error": "Корзина пуста"})

    custumer = request.user.client_profile
    total_amount = sum(item.product.price for item in cart_items)

    # Проверяем баланс
    if custumer.balance < total_amount:
        return JsonResponse({"success": False, "error": "Недостаточно баллов"})

    with transaction.atomic():
        # Блокируем строку клиента до конца транзакции
        custumer = Custumer.objects.select_for_update().get(pk=custumer.pk)

        # Создаем заказ
        order = Order.objects.create(
            customer=request.user, total_amount=total_amount, status="PENDING"
        )

        # Добавляем товары в заказ
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=1,
                price=cart_item.product.price,
            )

            # Записи о покупках будут созданы при завершении заказа

        # Списываем баллы
        custumer.balance -= total_amount
        custumer.save()

        # Создаем запись в истории баллов о списании
        PointsHistory.objects.create(
            custumer=custumer,
            points=-total_amount,  # Отрицательное значение для списания
            reason=ReasonTextChoices.PURCHASE,
            description=f"Покупка товаров из корзины (заказ #{order.id})",
            awarded_by=request.user,
        )

        # Очищаем корзину
        cart_items.delete()

    return JsonResponse(
        {
            "success": True,
            "message": f"Заказ #{order.id} создан успешно! Ожидает подтверждения.",  # noqa: E501
            "order_id": order.id,
        }
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_my_orders(request):
    """Просмотр заказов клиента."""
    status_filter = request.GET.get("status", "")
    search = request.GET.get("search", "")

    orders = (
        Order.objects.filter(customer=request.user)
        .select_related("customer")
        .prefetch_related("items__product")
    )

    if status_filter:
        orders = orders.filter(status=status_filter)

    if search:
        orders = orders.filter(id__icontains=search)

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

    return render(request, "customer/cabinet/my_orders.html", context)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_my_orders_detail(request, pk):
    """Детали заказа клиента."""
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    return render(
        request, "customer/cabinet/order_detail.html", {"order": order}
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_my_purchases(request):
    purchases = (
        Purchase.objects.filter(owner=request.user)
        .select_related("product", "order")
        .order_by("-id")
    )
    return render(
        request, "customer/cabinet/my_purchases.html", {"purchases": purchases}
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_points_history(request):
    """История получения баллов клиента."""
    custumer = getattr(request.user, "client_profile", None)
    if not custumer:
        return render(request, "page_404.html")

    # Получаем параметры фильтрации
    period = request.GET.get("period", "week")  # week, month, year, custom
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    # Определяем период по умолчанию (текущая неделя)
    today = timezone.now().date()
    if period == "week":
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == "month":
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == "year":
        date_from = today - timedelta(days=365)
        date_to = today
    elif period == "custom":
        if date_from and date_to:
            try:
                date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
                date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                # Если даты некорректные, используем текущую неделю
                date_from = today - timedelta(days=7)
                date_to = today
        else:
            # Если custom выбран, но даты не заданы, используем текущую неделю
            date_from = today - timedelta(days=7)
            date_to = today
    else:
        # По умолчанию - текущая неделя
        date_from = today - timedelta(days=7)
        date_to = today
        period = "week"

    points_history_records = (
        PointsHistory.objects.filter(
            custumer=custumer,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        .exclude(points=0)
        .select_related(
            "achievement",
            "competition_result__competition",
            "attendance_record__gr_class__groups_id",
            "attendance_record__gr_class__employe",
            "awarded_by",
        )
        .order_by("-created_at")
    )

    # Получаем все записи посещаемости с баллами за указанный период
    attendance_records = (
        GroupClassessCustumer.objects.filter(
            custumer=custumer,
            date__gte=date_from,
            date__lte=date_to,
            attendance_status__in=ATTENDANCE_SCORE.keys(),
        )
        .select_related("gr_class__groups_id", "gr_class__employe", "owner")
        .order_by("-date", "-class_time")
    )

    # Подготавливаем данные для отображения
    points_history = []
    total_points = 0
    # Обрабатываем записи из PointsHistory
    for record in points_history_records:
        total_points += record.points

        if record.reason == ReasonTextChoices.ACHIEVEMENT:
            points_type = "Достижение"
            points_description = (
                record.description
                or f"Достижение: {record.achievement.name if record.achievement else 'Неизвестно'}"  # noqa: E501
            )
            group_name = "-"
            class_name = "-"
            trainer_name = "-"
            evaluator_name = (
                record.awarded_by.get_full_name() if record.awarded_by else "-"
            )
            comment = ""
            attendance_status = ""

        elif record.reason == ReasonTextChoices.COMPETITION:
            points_type = "Соревнование"
            points_description = (
                record.description
                or f"Соревнование: {record.competition_result.competition.name if record.competition_result else 'Неизвестно'}"  # noqa: E501
            )
            group_name = "-"
            class_name = "-"
            trainer_name = "-"
            evaluator_name = (
                record.awarded_by.get_full_name() if record.awarded_by else "-"
            )
            comment = ""
            attendance_status = ""

        elif record.reason == ReasonTextChoices.ATTENDANCE:
            attendance = record.attendance_record
            if attendance:
                points_type = "Посещение занятия"
                points_description = "Баллы за посещение занятия"
                group_name = (
                    attendance.gr_class.groups_id.name
                    if attendance.gr_class.groups_id
                    else "Не указана"
                )
                class_name = (
                    attendance.gr_class.name
                    if attendance.gr_class.name
                    else "Занятие"
                )
                trainer_name = (
                    attendance.gr_class.employe.full_name
                    if attendance.gr_class.employe
                    else "Не указан"
                )
                evaluator_name = (
                    record.awarded_by.get_full_name()
                    if record.awarded_by
                    else "-"
                )
                comment = attendance.comment or ""
                attendance_status = attendance.attendance_status
            else:
                continue  # Пропускаем записи без связанного посещения

        elif record.reason == ReasonTextChoices.MANUAL:
            points_type = "Ручное начисление"
            points_description = (
                record.description or "Ручное начисление баллов"
            )
            group_name = "-"
            class_name = "-"
            trainer_name = "-"
            evaluator_name = (
                record.awarded_by.get_full_name() if record.awarded_by else "-"
            )
            comment = ""
            attendance_status = ""

        elif record.reason == ReasonTextChoices.PURCHASE:
            points_type = "Покупка товара"
            points_description = (
                record.description or "Списание баллов за покупку"
            )
            group_name = "-"
            class_name = "-"
            trainer_name = "-"
            evaluator_name = (
                record.awarded_by.get_full_name() if record.awarded_by else "-"
            )
            comment = ""
            attendance_status = ""

        else:
            points_type = record.get_reason_display()
            points_description = record.description or "Начисление баллов"
            group_name = "-"
            class_name = "-"
            trainer_name = "-"
            evaluator_name = (
                record.awarded_by.get_full_name() if record.awarded_by else "-"
            )
            comment = ""
            attendance_status = ""

        points_history.append(
            {
                "date": record.created_at.date(),
                "time": record.created_at.time(),
                "group_name": group_name,
                "class_name": class_name,
                "trainer_name": trainer_name,
                "points": record.points,
                "points_type": points_type,
                "points_description": points_description,
                "evaluator_name": evaluator_name,
                "comment": comment,
                "attendance_status": attendance_status,
                "source": record.reason,
            }
        )

    attendance_ids_in_history = set(
        points_history_records.filter(
            reason=ReasonTextChoices.ATTENDANCE
        ).values_list("attendance_record_id", flat=True)
    )

    for record in attendance_records:
        if record.id in attendance_ids_in_history:
            continue
        points = ATTENDANCE_SCORE.get(record.attendance_status, 0)
        total_points += points

        # Определяем тип получения баллов
        if record.attendance_status == "attended_10":
            points_type = "Отличная работа"
            points_description = (
                "Высокая оценка за отличное выполнение задания"
            )
        elif record.attendance_status == "attended_5":
            points_type = "Хорошая работа"
            points_description = "Хорошая оценка за качественное выполнение"
        elif record.attendance_status == "attended_4":
            points_type = "Удовлетворительно"
            points_description = "Средняя оценка за выполнение задания"
        elif record.attendance_status == "attended_3":
            points_type = "Посещение"
            points_description = "Баллы за посещение занятия"
        elif record.attendance_status == "attended_2":
            points_type = "Минимальное участие"
            points_description = "Минимальные баллы за участие"
        else:
            points_type = "Посещение"
            points_description = "Баллы за посещение"

        # Получаем имя того, кто поставил оценку
        evaluator_name = "-"
        if record.owner:
            evaluator_name = (
                record.owner.get_full_name() or record.owner.username
            )

        group_name = (
            record.gr_class.groups_id.name
            if record.gr_class.groups_id
            else "Не указана"
        )
        class_name = (
            record.gr_class.name if record.gr_class.name else "Занятие"
        )
        trainer_name = (
            record.gr_class.employe.full_name
            if record.gr_class.employe
            else "Не указан"
        )

        points_history.append(
            {
                "date": record.date,
                "time": record.class_time,
                "group_name": group_name,
                "class_name": class_name,
                "trainer_name": trainer_name,
                "points": points,
                "points_type": points_type,
                "points_description": points_description,
                "evaluator_name": evaluator_name,
                "comment": record.comment or "",
                "attendance_status": record.attendance_status,
            }
        )

    # Сортируем по дате и времени (новые записи сверху)
    # Обрабатываем None значения для корректной сортировки
    points_history.sort(
        key=lambda x: (
            x["date"] or datetime.min.date(),
            x["time"] or datetime.min.time(),
        ),
        reverse=True,
    )

    # Статистика
    stats = {
        "total_points": total_points,
        "total_classes": len(points_history),
        "avg_points_per_class": round(total_points / len(points_history), 2)
        if points_history
        else 0,
        "best_score": max([record["points"] for record in points_history])
        if points_history
        else 0,
        "period_days": (date_to - date_from).days + 1,
    }

    context = {
        "points_history": points_history,
        "stats": stats,
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "today": today,
    }

    return render(request, "customer/cabinet/points_history.html", context)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_my_subscriptions_history(request):
    """Детальная история абонементов, посещений и оплат клиента."""
    today = timezone.localdate()
    custumer = getattr(request.user, "client_profile", None)
    if not custumer:
        return render(request, "page_404.html")

    # Получаем параметры фильтрации
    period = request.GET.get("period", "all")  # all, active, expired
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if period == "month":
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == "year":
        date_from = today - timedelta(days=365)
        date_to = today
    elif period == "custom":
        if date_from and date_to:
            try:
                date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
                date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                # Если даты некорректные, показываем все время
                date_from = None
                date_to = None
        else:
            # Если custom выбран, но даты не заданы, показываем все время
            date_from = None
            date_to = None
    else:
        # По умолчанию - все время
        date_from = None
        date_to = None
        period = "all"

    # Получаем все абонементы клиента
    subscriptions_qs = (
        CustumerSubscription.objects.filter(custumer=custumer)
        .select_related("company", "owner")
        .prefetch_related("groups")
    )

    if date_from:
        subscriptions_qs = subscriptions_qs.filter(start_date__gte=date_from)
    if date_to:
        subscriptions_qs = subscriptions_qs.filter(end_date__lte=date_to)

    subscriptions = list(subscriptions_qs.order_by("-start_date"))

    # Получаем все посещения клиента
    attendance_qs = (
        GroupClassessCustumer.objects.filter(custumer=custumer)
        .exclude(attendance_status="none")
        .select_related(
            "gr_class__groups_id",
            "gr_class__employe",
            "owner",
            "used_subscription",
        )
        .order_by("-date", "-class_time")
    )

    if date_from:
        attendance_qs = attendance_qs.filter(date__gte=date_from)
    if date_to:
        attendance_qs = attendance_qs.filter(date__lte=date_to)

    attendances = list(attendance_qs)

    # Получаем все платежи клиента
    payments_qs = (
        CustumerSubscriptonPayment.objects.filter(custumer=custumer)
        .select_related("groups", "subscription", "cashier", "owner")
        .order_by("-summ_date", "-create_at")
    )

    if date_from:
        payments_qs = payments_qs.filter(summ_date__gte=date_from)
    if date_to:
        payments_qs = payments_qs.filter(summ_date__lte=date_to)

    payments = list(payments_qs)

    # Статистика
    active_subs = [
        s
        for s in subscriptions
        if s.start_date <= today <= s.end_date and not s.is_blok
    ]
    expired_subs = [s for s in subscriptions if s.end_date < today]

    stats = {
        "total_subscriptions": len(subscriptions),
        "active_subscriptions": len(active_subs),
        "expired_subscriptions": len(expired_subs),
        "total_attendances": len(attendances),
        "total_payments": len(payments),
        "total_paid": sum(p.summ or 0 for p in payments if p.is_pay),
        "total_unpaid": sum(p.summ or 0 for p in payments if not p.is_pay),
    }

    context = {
        "subscriptions": subscriptions,
        "attendances": attendances,
        "payments": payments,
        "stats": stats,
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "today": today,
    }

    return render(
        request, "customer/cabinet/subscriptions_history.html", context
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def team_member_detail(request, member_id):
    """Детальная страница участника команды."""
    current_custumer = getattr(request.user, "client_profile", None)
    if not current_custumer:
        return render(request, "page_404.html")

    # Получаем участника команды
    try:
        member = (
            Custumer.objects.select_related(
                "user", "sport_category", "company"
            )
            .prefetch_related("achievements", "competitions", "groups")
            .get(
                id=member_id,
                company=current_custumer.company,
            )
        )
    except Custumer.DoesNotExist:
        return render(request, "page_404.html")

    # Получаем все результаты соревнований участника
    competition_results = (
        CustumerCompetitionResult.objects.filter(
            customer_id=member.id if member.id else None,
            is_disqualified=False,
        )
        .select_related("competition", "sport_category")
        .order_by("-competition__date")[:20]
    )  # Последние 20 результатов

    # Получаем первые 5 достижений участника
    achievements = member.achievements.all().order_by("-id")[:6]

    # Вычисляем средний балл из всех посещений
    all_attendances = GroupClassessCustumer.objects.filter(
        custumer=member, attendance_status__in=ATTENDANCE_SCORE.keys()
    )

    avg_score = 0
    if all_attendances.exists():
        total_score = sum(
            ATTENDANCE_SCORE.get(att.attendance_status, 0)
            for att in all_attendances
        )
        avg_score = total_score / all_attendances.count()

    # Получаем группы участника
    groups = member.groups.all()

    # Статистика
    stats = {
        "total_competitions": competition_results.count(),
        "total_achievements": member.achievements.count(),
        "total_attendances": all_attendances.count(),
        "avg_score": round(avg_score, 2),
        "groups_count": groups.count(),
    }

    context = {
        "member": member,
        "competition_results": competition_results,
        "achievements": achievements,
        "groups": groups,
        "stats": stats,
        "current_custumer": current_custumer,
    }

    return render(request, "customer/cabinet/team_member_detail.html", context)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_member_achievements(request, member_id):
    """AJAX endpoint для загрузки дополнительных достижений участника."""
    current_custumer = getattr(request.user, "client_profile", None)
    if not current_custumer:
        return JsonResponse(
            {"success": False, "error": "Пользователь не найден"}, status=404
        )

    try:
        # Получаем участника команды
        member = Custumer.objects.get(
            id=member_id,
            company=current_custumer.company,
        )
    except Custumer.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Участник не найден"}, status=404
        )

    # Получаем параметры пагинации
    offset = int(request.GET.get("offset", 6))
    limit = 5

    # Получаем достижения с пагинацией
    achievements = member.achievements.all().order_by(
        "-id"
    )[
        offset : offset  # noqa: E203
        + limit
    ]

    # Подготавливаем данные для JSON
    achievements_data = []
    for achievement in achievements:
        achievements_data.append(
            {
                "id": achievement.id,
                "name": achievement.name,
                "description": achievement.description or "",
            }
        )

    response_data = {
        "success": True,
        "achievements": achievements_data,
        "has_more": len(achievements_data) == limit,
    }

    return JsonResponse(response_data)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_member_competitions(request, member_id):
    """AJAX endpoint для загрузки соревнований участника с пагинацией."""
    current_custumer = getattr(request.user, "client_profile", None)
    if not current_custumer:
        return JsonResponse(
            {"success": False, "error": "Пользователь не найден"}, status=404
        )

    try:
        # Получаем участника команды
        member = Custumer.objects.get(
            id=member_id,
            company=current_custumer.company,
        )
    except Custumer.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Участник не найден"}, status=404
        )

    # Получаем параметры пагинации
    offset = int(request.GET.get("offset", 0))
    limit = 5

    # Получаем уникальные соревнования участника с пагинацией
    competitions = (
        CustumerCompetitionResult.objects.filter(
            customer_id=member.id if member.id else None,
            is_disqualified=False,
        )
        .select_related("competition")
        .values(
            "competition__id",
            "competition__name",
            "competition__date",
            "competition__location",
        )
        .distinct()
        .order_by("-competition__date")[offset : offset + limit]  # noqa: E203
    )

    # Подготавливаем данные для JSON
    competitions_data = []
    for comp in competitions:
        competitions_data.append(
            {
                "id": comp["competition__id"],
                "name": comp["competition__name"],
                "date": (
                    comp["competition__date"].strftime("%d.%m.%Y")
                    if comp["competition__date"]
                    else ""
                ),
                "location": comp["competition__location"] or "",
            }
        )

    response_data = {
        "success": True,
        "competitions": competitions_data,
        "has_more": len(competitions_data) == limit,
    }

    return JsonResponse(response_data)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_competition_results(request, member_id, competition_id):
    """AJAX endpoint для получения результатов конкретного соревнования."""
    current_custumer = getattr(request.user, "client_profile", None)
    if not current_custumer:
        return JsonResponse(
            {"success": False, "error": "Пользователь не найден"}, status=404
        )

    try:
        # Получаем участника команды
        member = Custumer.objects.get(
            id=member_id,
            company=current_custumer.company,
        )
    except Custumer.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Участник не найден"}, status=404
        )

    # Получаем результаты соревнования для участника
    results = (
        CustumerCompetitionResult.objects.filter(
            customer_id=member.id if member.id else None,
            competition_id=competition_id,
            is_disqualified=False,
        )
        .select_related("competition", "sport_category")
        .order_by("distance", "result_time_ms")
    )

    # Подготавливаем данные для JSON
    results_data = []
    for result in results:
        results_data.append(
            {
                "id": result.id,
                "distance": result.distance,
                "discipline": result.discipline or "",
                "style": result.get_style_display,
                "result_time": result.formatted_time,
                "place": result.place,
                "sport_category": (
                    result.sport_category.name if result.sport_category else ""
                ),
            }
        )

    # Получаем информацию о соревновании
    competition_info = None
    if results.exists():
        comp = results.first().competition
        competition_info = {
            "name": comp.name,
            "date": comp.date.strftime("%d.%m.%Y") if comp.date else "",
            "location": comp.location or "",
        }

    response_data = {
        "success": True,
        "competition": competition_info,
        "results": results_data,
    }

    return JsonResponse(response_data)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_kilometers_history(request):
    """История километров клиента по занятиям и соревнованиям."""
    custumer = getattr(request.user, "client_profile", None)
    if not custumer:
        return render(request, "page_404.html")

    # Получаем параметры фильтрации
    period = request.GET.get("period", "month")  # week, month, year, custom
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    group_id = request.GET.get("group_id")

    # Определяем период по умолчанию (текущий месяц)
    today = timezone.now().date()
    if period == "week":
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == "month":
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == "year":
        date_from = today - timedelta(days=365)
        date_to = today
    elif period == "custom":
        if date_from and date_to:
            try:
                date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
                date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                # Если даты некорректные, используем текущий месяц
                date_from = today - timedelta(days=30)
                date_to = today
        else:
            # Если custom выбран, но даты не заданы, используем текущий месяц
            date_from = today - timedelta(days=30)
            date_to = today
    else:
        # По умолчанию - текущий месяц
        date_from = today - timedelta(days=30)
        date_to = today
        period = "month"

    # Получаем все посещения клиента с оценками за указанный период
    attendance_qs = (
        GroupClassessCustumer.objects.filter(
            custumer=custumer,
            date__gte=date_from,
            date__lte=date_to,
            attendance_status__in=ATTENDANCE_SCORE.keys(),
        )
        .select_related(
            "gr_class__groups_id",
            "gr_class__employe",
            "owner",
        )
        .order_by("-date", "-class_time")
    )

    # Фильтруем по группе, если выбрана
    if group_id:
        attendance_qs = attendance_qs.filter(gr_class__groups_id__id=group_id)

    attendances = list(attendance_qs)

    # Получаем все программы занятий одним запросом
    gr_class_ids = [att.gr_class_id for att in attendances if att.gr_class_id]
    program_distances = {}
    if gr_class_ids:
        programs = ClasessProgramm.objects.filter(
            classes_id__in=gr_class_ids
        ).values("classes_id", "distance", "stages", "style", "comments")

        for program in programs:
            program_distances[program["classes_id"]] = {
                "distance": (
                    float(program["distance"]) if program["distance"] else 0
                ),
                "stages": program["stages"],
                "style": program["style"],
                "comments": program["comments"],
            }

    # Получаем результаты соревнований клиента за указанный период
    competition_results = (
        CustumerCompetitionResult.objects.filter(
            customer=custumer,
            competition__date__gte=date_from,
            competition__date__lte=date_to,
        )
        .select_related("competition")
        .order_by("-competition__date")
    )

    # Подготавливаем данные для отображения
    kilometers_history = []
    total_kilometers = 0
    total_sessions = 0

    # Обрабатываем занятия с дистанциями
    for attendance in attendances:
        if not attendance.gr_class_id:
            continue

        # Получаем дистанцию из программы занятия
        program_data = program_distances.get(attendance.gr_class_id, {})
        distance_meters = program_data.get("distance", 0)

        # Пропускаем занятия без дистанции
        if distance_meters <= 0:
            continue

        distance_km = round(distance_meters / 1000, 2)

        # Получаем баллы за посещение
        points = ATTENDANCE_SCORE.get(attendance.attendance_status, 0)

        # Определяем тип оценки
        if attendance.attendance_status == "attended_10":
            evaluation_type = "Отлично"
            evaluation_description = "Высокая оценка за отличное выполнение"
        elif attendance.attendance_status == "attended_5":
            evaluation_type = "Хорошо"
            evaluation_description = (
                "Хорошая оценка за качественное выполнение"
            )
        elif attendance.attendance_status == "attended_4":
            evaluation_type = "Удовлетворительно"
            evaluation_description = "Средняя оценка за выполнение"
        elif attendance.attendance_status == "attended_3":
            evaluation_type = "Посещение"
            evaluation_description = "Баллы за посещение занятия"
        elif attendance.attendance_status == "attended_2":
            evaluation_type = "Минимальное участие"
            evaluation_description = "Минимальные баллы за участие"
        else:
            evaluation_type = "Посещение"
            evaluation_description = "Баллы за посещение"

        # Получаем имя тренера
        trainer_name = (
            attendance.gr_class.employe.full_name
            if attendance.gr_class.employe
            else "Не указан"
        )

        # Получаем имя того, кто поставил оценку
        evaluator_name = "-"
        if attendance.owner:
            evaluator_name = (
                attendance.owner.get_full_name() or attendance.owner.username
            )

        group_name = (
            attendance.gr_class.groups_id.name
            if attendance.gr_class.groups_id
            else "Не указана"
        )

        class_name = (
            attendance.gr_class.name if attendance.gr_class.name else "Занятие"
        )

        kilometers_history.append(
            {
                "date": attendance.date,
                "time": attendance.class_time,
                "group_name": group_name,
                "class_name": class_name,
                "trainer_name": trainer_name,
                "distance_km": distance_km,
                "distance_meters": distance_meters,
                "points": points,
                "evaluation_type": evaluation_type,
                "evaluation_description": evaluation_description,
                "evaluator_name": evaluator_name,
                "comment": attendance.comment or "",
                "attendance_status": attendance.attendance_status,
                "stages": program_data.get("stages", ""),
                "style": program_data.get("style", ""),
                "program_comments": program_data.get("comments", ""),
                "type": "training",
            }
        )

        total_kilometers += distance_km
        total_sessions += 1

    # Обрабатываем соревнования
    for result in competition_results:
        distance_km = round(result.distance / 1000, 2)

        # Формируем описание результата
        if result.formatted_time:
            evaluation_description = f"Результат: {result.formatted_time}"
        else:
            evaluation_description = "Участие"

        # Формируем комментарий с местом
        comment = ""
        if hasattr(result, "place") and result.place:
            comment = f"Место: {result.place}"

        kilometers_history.append(
            {
                "date": result.competition.date,
                "time": None,
                "group_name": "Соревнование",
                "class_name": result.competition.name,
                "trainer_name": "-",
                "distance_km": distance_km,
                "distance_meters": result.distance,
                "points": 0,  # Соревнования не дают баллы в этой системе
                "evaluation_type": "Соревнование",
                "evaluation_description": evaluation_description,
                "evaluator_name": "-",
                "comment": comment,
                "attendance_status": "",
                "stages": result.discipline or "",
                "style": result.get_style_display,
                "program_comments": "",
                "type": "competition",
            }
        )

        total_kilometers += distance_km
        total_sessions += 1

    # Сортируем по дате и времени (новые записи сверху)
    kilometers_history.sort(
        key=lambda x: (
            x["date"] or datetime.min.date(),
            x["time"] or datetime.min.time(),
        ),
        reverse=True,
    )

    # Получаем группы клиента для фильтра
    groups = custumer.groups.all()

    # Статистика
    stats = {
        "total_kilometers": round(total_kilometers, 2),
        "total_sessions": total_sessions,
        "avg_kilometers_per_session": (
            round(total_kilometers / total_sessions, 2)
            if total_sessions
            else 0
        ),
        "period_days": (date_to - date_from).days + 1,
        "avg_kilometers_per_day": round(
            total_kilometers / ((date_to - date_from).days + 1), 2
        ),
    }

    # Дополнительная статистика по группам
    group_stats = {}
    for group in groups:
        group_attendances = [
            h
            for h in kilometers_history
            if h["group_name"] == group.name and h["type"] == "training"
        ]
        group_total_km = sum(h["distance_km"] for h in group_attendances)
        group_sessions = len(group_attendances)

        group_stats[group.name] = {
            "total_kilometers": round(group_total_km, 2),
            "sessions": group_sessions,
            "avg_per_session": (
                round(group_total_km / group_sessions, 2)
                if group_sessions
                else 0
            ),
        }

    # Добавляем статистику по соревнованиям
    competition_attendances = [
        h for h in kilometers_history if h["type"] == "competition"
    ]
    if competition_attendances:
        competition_total_km = sum(
            h["distance_km"] for h in competition_attendances
        )
        group_stats["Соревнования"] = {
            "total_kilometers": round(competition_total_km, 2),
            "sessions": len(competition_attendances),
            "avg_per_session": (
                round(competition_total_km / len(competition_attendances), 2)
                if competition_attendances
                else 0
            ),
        }

    context = {
        "kilometers_history": kilometers_history,
        "stats": stats,
        "group_stats": group_stats,
        "groups": groups,
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "group_id": group_id,
        "today": today,
    }

    return render(request, "customer/cabinet/kilometers_history.html", context)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_group_detail(request, group_id):
    """Детализация по конкретной группе с информацией о всех участниках."""
    custumer = getattr(request.user, "client_profile", None)
    if not custumer:
        return render(request, "page_404.html")

    # Получаем группу
    try:
        group = GroupsClass.objects.select_related(
            "company", "type_sport"
        ).get(id=group_id, company=custumer.company)
    except GroupsClass.DoesNotExist:
        return render(request, "page_404.html")

    # Проверяем, что клиент состоит в этой группе
    if group not in custumer.groups.all():
        return render(request, "page_404.html")

    # Получаем всех участников группы
    group_members = group.custumer_set.select_related(
        "user", "sport_category"
    ).prefetch_related("achievements")

    # Получаем рейтинги всех участников группы одним запросом
    member_attendances = (
        GroupClassessCustumer.objects.filter(
            gr_class__groups_id=group,
            custumer__in=group_members,
            attendance_status__in=ATTENDANCE_SCORE.keys(),
        )
        .values("custumer")
        .annotate(
            avg_score=Avg(
                Case(
                    *(
                        When(attendance_status=k, then=v)
                        for k, v in ATTENDANCE_SCORE.items()
                    ),
                    output_field=IntegerField(),
                )
            )
        )
    )

    # Создаем словарь средних баллов
    member_avg_dict = {
        a["custumer"]: a["avg_score"] or 0 for a in member_attendances
    }

    # Добавляем участников без оценок с нулевым средним баллом
    for member_id in group_members.values_list("id", flat=True):
        if member_id not in member_avg_dict:
            member_avg_dict[member_id] = 0

    # Сортируем участников по рейтингу
    sorted_members = sorted(
        member_avg_dict.items(), key=lambda x: x[1], reverse=True
    )

    # Собираем данные о каждом участнике
    members_data = {}
    for i, (member_id, avg_score) in enumerate(sorted_members):
        member = group_members.get(id=member_id)
        if member:
            # Получаем достижения участника
            achievements = list(member.achievements.all())[:5]

            # Получаем результаты соревнований
            competition_results = []
            if member.user:
                competition_results = list(
                    CustumerCompetitionResult.objects.filter(
                        customer_id=member.id, is_disqualified=False
                    )
                    .select_related("competition")
                    .order_by("-competition__date")[:5]
                )

            members_data[member_id] = {
                "member": member,
                "avg_score": avg_score,
                "place": i + 1,
                "achievements": achievements,
                "competition_results": competition_results,
            }

    # Находим данные текущего клиента
    current_user_data = members_data.get(custumer.id, {})

    context = {
        "group": group,
        "members_data": members_data,
        "current_user_data": current_user_data,
        "total_members": len(group_members),
    }

    return render(request, "customer/cabinet/group_detail.html", context)
