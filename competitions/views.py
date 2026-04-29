from datetime import datetime

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from competitions.models import Competitions, CustumerCompetitionResult
from competitions.schemas import StatusTextChoices
from competitions.services import (
    get_competition_context,
    get_competition_results_data,
)
from competitions.utils import (
    assign_rank_to_customer,
    get_competition_results_with_ranks,
    get_customer_with_rank_info,
    get_sport_categories_ordered,
)
from custumer.models import Custumer, SportCategory
from employe.utils import (
    can_create_competitions,
    can_edit_competitions,
    can_manage_competition_results,
    can_view_competitions,
)


def _check_user_permissions(user, permission_func=None):
    """
    Оптимизированная проверка прав пользователя.

    Args:
        user: Пользователь для проверки
        permission_func: Функция для проверки конкретного права

    Returns:
        tuple: (is_admin, is_assistant, has_permission)
    """
    user_groups = list(user.groups.values_list("name", flat=True))
    is_admin = "admin" in user_groups
    is_assistant = "assistant" in user_groups

    if permission_func and is_assistant:
        has_permission = permission_func(user)
    else:
        has_permission = is_admin

    return is_admin, is_assistant, has_permission


def _get_competition_with_company_access(competition_id, user):
    """
    Получает соревнование с проверкой доступа по компании.

    Args:
        competition_id: ID соревнования
        user: Пользователь для проверки доступа

    Returns:
        Competitions: Объект соревнования или 404
    """
    return get_object_or_404(
        Competitions.objects.select_related("owner"),
        id=competition_id,
        owner__company=user.company,
    )


def create_competition(request):
    """Создание соревнования."""
    # Оптимизированная проверка прав
    _, is_assistant, has_permission = _check_user_permissions(
        request.user, can_create_competitions
    )
    base_template = "base2.html" if is_assistant else "base.html"
    if not has_permission:
        return render(request, "page_404.html")

    status_choices = Competitions._meta.get_field("status").choices

    if request.method == "POST":
        name = request.POST.get("name")
        date_str = request.POST.get("date")
        end_date_str = request.POST.get("end_date", "")
        location = request.POST.get("location")
        status = request.POST.get("status", StatusTextChoices.OPEN.value)
        try:
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
                if end_date < date:
                    return render(
                        request,
                        "competitions/create.html",
                        {
                            "error": (
                                "Дата окончания должна быть больше даты начала"
                            ),
                            "name": name,
                            "location": location,
                            "status": status,
                            "date": date_str,
                            "end_date": end_date_str,
                            "status_choices": status_choices,
                            "base_template": base_template,
                        },
                    )
            else:
                end_date = None
        except (ValueError, TypeError):
            return render(
                request,
                "competitions/create.html",
                {
                    "error": "Дата должна быть в формате дд.мм.гггг",
                    "name": name,
                    "location": location,
                    "status": status,
                    "date": date_str,
                    "end_date": end_date_str,
                    "status_choices": status_choices,
                    "base_template": base_template,
                },
            )
        Competitions.objects.create(
            name=name,
            date=date,
            location=location,
            status=status,
            owner=request.user,
            end_date=end_date,
        )
        return redirect("competitions:competitions_list")

    return render(
        request,
        "competitions/create.html",
        {"status_choices": status_choices, "base_template": base_template},
    )


def get_competitions(request):
    """Вывод списка соревнований."""
    # Оптимизированная проверка прав
    is_admin, is_assistant, has_permission = _check_user_permissions(
        request.user, can_view_competitions
    )
    if not has_permission:
        return render(request, "page_404.html")

    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    end_date = request.GET.get("end_date", "")

    # Фильтруем соревнования по компании пользователя
    competitions = Competitions.objects.select_related("owner").filter(
        owner__company=request.user.company
    )

    if search:
        competitions = competitions.filter(name__icontains=search)
    if date and end_date:
        try:
            date_obj = datetime.strptime(date, "%d.%m.%Y").date()
            end_date_obj = datetime.strptime(end_date, "%d.%m.%Y").date()
            competitions = competitions.filter(
                date__gte=date_obj,
                end_date__lte=end_date_obj,
            )
        except ValueError:
            pass
    elif date:
        try:
            date_obj = datetime.strptime(date, "%d.%m.%Y").date()
            competitions = competitions.filter(date__gte=date_obj)
        except ValueError:
            pass
    elif end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%d.%m.%Y").date()
            competitions = competitions.filter(end_date__lte=end_date_obj)
        except ValueError:
            pass
    competitions = competitions.order_by("-date", "-end_date")
    page = int(request.GET.get("page", 1))
    per_page = 8
    paginator = Paginator(competitions, per_page)
    page_obj = paginator.get_page(page)

    # Используем уже полученную информацию о роли
    base_template = "base2.html" if is_assistant else "base.html"
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(
            request,
            "competitions/_competitions_list.html",
            {"page_obj": page_obj, "base_template": base_template},
        )
    return render(
        request,
        "competitions/index.html",
        {"page_obj": page_obj, "base_template": base_template},
    )


def get_competition_details(request, pk):
    """Вывод деталей соревнования."""
    # Оптимизированная проверка прав
    _, is_assistant, has_permission = _check_user_permissions(
        request.user, can_view_competitions
    )
    if not has_permission:
        return render(request, "page_404.html")

    context_data = get_competition_context(pk, request.user)
    base_template = "base2.html" if is_assistant else "base.html"
    return render(
        request,
        "competitions/details.html",
        {
            **context_data,
            "base_template": base_template,
        },
    )


def update_competition(request, pk):
    """Обновление соревнования."""
    # Оптимизированная проверка прав
    _, is_assistant, has_permission = _check_user_permissions(
        request.user, can_edit_competitions
    )
    if not has_permission:
        return render(request, "page_404.html")

    # Получаем соревнование с проверкой доступа по компании
    competition = _get_competition_with_company_access(pk, request.user)
    base_template = "base2.html" if is_assistant else "base.html"
    status_choices = Competitions._meta.get_field("status").choices

    if request.method == "POST":
        name = request.POST.get("name")
        date_str = request.POST.get("date")
        end_date_str = request.POST.get("end_date", "")
        location = request.POST.get("location")
        status = request.POST.get("status", StatusTextChoices.OPEN.value)
        try:
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
                if end_date < date:
                    return render(
                        request,
                        "competitions/update.html",
                        {
                            "error": (
                                "Дата окончания должна быть больше даты начала"
                            ),
                            "name": name,
                            "location": location,
                            "status": status,
                            "date": date,
                            "end_date": end_date,
                            "competition": competition,
                            "status_choices": status_choices,
                            "base_template": base_template,
                        },
                    )
            else:
                end_date = None
        except (ValueError, TypeError):
            return render(
                request,
                "competitions/update.html",
                {
                    "error": "Дата должна быть в формате дд.мм.гггг",
                    "name": name,
                    "location": location,
                    "status": status,
                    "date": date_str,
                    "end_date": end_date_str,
                    "competition": competition,
                    "status_choices": status_choices,
                    "base_template": base_template,
                },
            )
        competition.name = name
        competition.date = date
        competition.end_date = end_date
        competition.location = location
        competition.status = status
        competition.save()
        return redirect("competitions:competitions_list")

    return render(
        request,
        "competitions/update.html",
        {
            "competition": competition,
            "status_choices": status_choices,
            "base_template": base_template,
        },
    )


def delete_competition(request, pk):
    """Удаление соревнования."""
    # Оптимизированная проверка прав
    _, _, has_permission = _check_user_permissions(
        request.user, can_edit_competitions
    )
    if not has_permission:
        return render(request, "page_404.html")

    # Получаем соревнование с проверкой доступа по компании
    competition = _get_competition_with_company_access(pk, request.user)
    competition.delete()
    return redirect("competitions:competitions_list")


def add_customers_to_competition(request, pk):
    """Добавление пользователей в соревнование."""
    # Оптимизированная проверка прав
    _, _, has_permission = _check_user_permissions(
        request.user, can_edit_competitions
    )
    if not has_permission:
        return render(request, "page_404.html")

    # Получаем соревнование с проверкой доступа по компании
    competition = _get_competition_with_company_access(pk, request.user)
    customers = request.POST.getlist("customers")
    competition.customers.add(*customers)
    return redirect("competitions:get_competition_details", pk=pk)


def delete_customers_from_competition(request, pk):
    """Удаление пользователей из соревнования."""
    # Оптимизированная проверка прав
    _, _, has_permission = _check_user_permissions(
        request.user, can_edit_competitions
    )
    if not has_permission:
        return render(request, "page_404.html")

    # Получаем соревнование с проверкой доступа по компании
    competition = _get_competition_with_company_access(pk, request.user)
    customers = request.POST.getlist("customers")
    competition.customers.remove(*customers)
    return redirect("competitions:competitions_list")


def save_competition_result(request, competition_id, customer_id):
    """Сохранение результатов соревнования."""
    # Оптимизированная проверка прав
    _, _, has_permission = _check_user_permissions(
        request.user, can_manage_competition_results
    )
    if not has_permission:
        return JsonResponse(
            {
                "success": False,
                "error": "Нет прав для выполнения этого действия",
            }
        )

    # Получаем соревнование с проверкой доступа по компании
    competition = _get_competition_with_company_access(
        competition_id, request.user
    )

    # Получаем клиента с проверкой компании
    customer = get_object_or_404(
        Custumer.objects.select_related("user"),
        id=customer_id,
        company=request.user.company,
    )

    distance = request.POST.get("distance", "").strip()
    discipline = request.POST.get("discipline", "").strip()
    style = request.POST.get("style", "").strip()
    result_time = request.POST.get("result_time", "").strip()
    place = request.POST.get("place", "").strip()
    assign_rank = request.POST.get("assign_rank", "").strip()
    is_disqualified = request.POST.get("is_disqualified") == "on"
    disqualification_comment = request.POST.get(
        "disqualification_comment", ""
    ).strip()

    # Валидация дистанции
    try:
        distance_val = float(distance)
        if distance_val <= 0:
            raise ValueError
    except ValueError:
        return JsonResponse(
            {
                "success": False,
                "error": "Дистанция должна быть положительным числом (метры).",
            }
        )

    # Валидация времени и места только если не дисквалифицирован
    time_ms = None
    place_val = None

    if not is_disqualified:
        # Валидация времени
        if not result_time:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Время обязательно для недисквалифицированных участников",  # noqa: E501
                }
            )
        try:
            # Парсим формат мм:сс:ммм
            parts = result_time.split(":")
            if len(parts) != 3:
                raise ValueError("Неверный формат")

            minutes = int(parts[0])
            seconds = int(parts[1])
            milliseconds = int(parts[2])

            # Валидация
            if not (0 <= minutes <= 99):
                raise ValueError("Минуты должны быть от 0 до 99")
            if not (0 <= seconds <= 59):
                raise ValueError("Секунды должны быть от 0 до 59")
            if not (0 <= milliseconds <= 999):
                raise ValueError("Миллисекунды должны быть от 0 до 999")

            # Преобразование в миллисекунды
            time_ms = (minutes * 60 + seconds) * 1000 + milliseconds

            if time_ms <= 0:
                raise ValueError("Время должно быть больше нуля")

        except (ValueError, IndexError) as e:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Время должно быть в формате мм:сс:ммм. {str(e)}",  # noqa: E501
                }
            )

        # Валидация места
        if not place:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Место обязательно для недисквалифицированных участников",  # noqa: E501
                }
            )
        try:
            place_val = int(place)
            if place_val < 1:
                raise ValueError
        except ValueError:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Место должно быть положительным целым числом.",
                }
            )
    else:
        # При дисквалификации проверяем, что есть комментарий
        if not disqualification_comment:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Причина дисквалификации обязательна",
                }
            )

    # Получаем разряд, если указан
    sport_category = None
    if assign_rank and assign_rank != "0":
        try:
            sport_category = SportCategory.objects.get(id=assign_rank)

            # Получаем клиента с информацией о разряде
            customer = get_customer_with_rank_info(
                customer_id, request.user.company
            )

            if customer:
                # Присваиваем разряд клиенту (если можно)
                # и сохраняем в результате
                success, message, customer_updated = assign_rank_to_customer(
                    customer,
                    sport_category,
                    None,  # result еще не создан
                )

                if not success:
                    # Если произошла ошибка, не создаем результат
                    return JsonResponse({"success": False, "error": message})

                # Разряд всегда сохраняется в результате,
                # даже если клиенту не присвоен
                # sport_category остается установленным
            else:
                # Если клиент не найден, не присваиваем разряд
                sport_category = None

        except SportCategory.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Указанный разряд не найден"}
            )

    # Создаем новый результат (теперь можно добавлять множественные дистанции)
    CustumerCompetitionResult.objects.create(
        competition=competition,
        customer=customer,
        distance=distance_val,
        discipline=discipline,
        style=style,
        result_time_ms=time_ms,
        place=place_val,
        is_disqualified=is_disqualified,
        disqualification_comment=disqualification_comment,
        sport_category=sport_category,
    )

    return JsonResponse({"success": True})


def get_competition_results(request, competition_id, customer_id):
    """Получение результатов соревнования для конкретного участника."""
    # Оптимизированная проверка прав
    _, is_assistant, has_permission = _check_user_permissions(
        request.user, can_manage_competition_results
    )
    if not has_permission:
        return JsonResponse(
            {
                "success": False,
                "error": "Нет прав для выполнения этого действия",
            }
        )

    # Получаем соревнование с проверкой доступа по компании
    competition = _get_competition_with_company_access(
        competition_id, request.user
    )
    base_template = "base2.html" if is_assistant else "base.html"
    # Получаем клиента с информацией о разряде в одном запросе
    customer = get_customer_with_rank_info(customer_id, request.user.company)
    if not customer:
        return JsonResponse(
            {
                "success": False,
                "error": "Клиент не найден",
            }
        )

    # Получаем все результаты для этого участника в этом соревновании
    results = get_competition_results_with_ranks(competition.id, customer.id)

    # Получаем разряды, отсортированные по уровню
    sport_categories = get_sport_categories_ordered()

    return JsonResponse(
        {
            "success": True,
            "customer_name": customer.full_name,
            "results": [
                {
                    "id": result.id,
                    "distance": result.distance,
                    "discipline": result.discipline or "",
                    "style": result.get_style_display,
                    "result_time": result.format_time(),
                    "place": result.place,
                    "is_disqualified": result.is_disqualified,
                    "disqualification_comment": result.disqualification_comment
                    or "",
                    "sport_category": (
                        result.sport_category.name
                        if result.sport_category
                        else None
                    ),
                }
                for result in results
            ],
            "sport_categories": [
                {"id": cat.id, "name": cat.name} for cat in sport_categories
            ],
            "current_rank": (
                customer.sport_category.id if customer.sport_category else None
            ),
            "base_template": base_template,
        }
    )


def get_competition_results_overview(request, competition_id):
    """Возвращает агрегированные результаты соревнования для AJAX."""
    _, _, has_permission = _check_user_permissions(
        request.user, can_view_competitions
    )
    if not has_permission:
        return JsonResponse(
            {"success": False, "error": "Нет прав для просмотра результатов"},
            status=403,
        )

    _get_competition_with_company_access(competition_id, request.user)

    data = get_competition_results_data(competition_id, request.user)
    return JsonResponse({"success": True, "data": data})


def update_competition_result(request, result_id):
    """Обновление результата соревнования."""
    # Оптимизированная проверка прав
    _, _, has_permission = _check_user_permissions(
        request.user, can_manage_competition_results
    )
    if not has_permission:
        return JsonResponse(
            {
                "success": False,
                "error": "Нет прав для выполнения этого действия",
            }
        )

    # Получаем результат с проверкой доступа по компании
    result = get_object_or_404(
        CustumerCompetitionResult.objects.select_related("competition__owner"),
        id=result_id,
        competition__owner__company=request.user.company,
    )

    distance = request.POST.get("distance", "").strip()
    discipline = request.POST.get("discipline", "").strip()
    style = request.POST.get("style", "").strip()
    result_time = request.POST.get("result_time", "").strip()
    place = request.POST.get("place", "").strip()
    assign_rank = request.POST.get("assign_rank", "").strip()
    is_disqualified = request.POST.get("is_disqualified") == "on"
    disqualification_comment = request.POST.get(
        "disqualification_comment", ""
    ).strip()

    # Валидация дистанции
    try:
        distance_val = float(distance)
        if distance_val <= 0:
            raise ValueError
    except ValueError:
        return JsonResponse(
            {
                "success": False,
                "error": "Дистанция должна быть положительным числом (метры).",
            }
        )

    # Валидация времени и места только если не дисквалифицирован
    time_ms = None
    place_val = None

    if not is_disqualified:
        # Валидация времени
        if not result_time:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Время обязательно для недисквалифицированных участников",  # noqa: E501
                }
            )
        try:
            # Парсим формат мм:сс:ммм
            parts = result_time.split(":")
            if len(parts) != 3:
                raise ValueError("Неверный формат")

            minutes = int(parts[0])
            seconds = int(parts[1])
            milliseconds = int(parts[2])

            # Валидация
            if not (0 <= minutes <= 99):
                raise ValueError("Минуты должны быть от 0 до 99")
            if not (0 <= seconds <= 59):
                raise ValueError("Секунды должны быть от 0 до 59")
            if not (0 <= milliseconds <= 999):
                raise ValueError("Миллисекунды должны быть от 0 до 999")

            # Преобразование в миллисекунды
            time_ms = (minutes * 60 + seconds) * 1000 + milliseconds

            if time_ms <= 0:
                raise ValueError("Время должно быть больше нуля")

        except (ValueError, IndexError) as e:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Время должно быть в формате мм:сс:ммм. {str(e)}",  # noqa: E501
                }
            )

        # Валидация места
        if not place:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Место обязательно для недисквалифицированных участников",  # noqa: E501
                }
            )
        try:
            place_val = int(place)
            if place_val < 1:
                raise ValueError
        except ValueError:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Место должно быть положительным целым числом.",
                }
            )
    else:
        # При дисквалификации проверяем, что есть комментарий
        if not disqualification_comment:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Причина дисквалификации обязательна",
                }
            )

    # Получаем разряд, если указан
    sport_category = None
    if assign_rank and assign_rank != "0":
        try:
            sport_category = SportCategory.objects.get(id=assign_rank)
            # Получаем клиента с информацией о разряде
            customer = get_customer_with_rank_info(
                result.customer.id, request.user.company
            )

            if customer:
                # Присваиваем разряд с проверкой логики
                success, message, customer_updated = assign_rank_to_customer(
                    customer, sport_category, result
                )

                if not success:
                    # Если произошла ошибка, не обновляем результат
                    return JsonResponse({"success": False, "error": message})

                # Разряд всегда сохраняется в результате,
                # даже если клиенту не присвоен
                # sport_category остается установленным
            else:
                # Если клиент не найден, не присваиваем разряд
                sport_category = None

        except SportCategory.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Указанный разряд не найден"}
            )

    # Обновляем результат
    result.distance = distance_val
    result.discipline = discipline
    result.style = style
    result.result_time_ms = time_ms
    result.place = place_val
    result.is_disqualified = is_disqualified
    result.disqualification_comment = disqualification_comment
    result.sport_category = sport_category
    result.save()

    return JsonResponse({"success": True})


def delete_competition_result(request, result_id):
    """Удаление результата соревнования."""
    # Оптимизированная проверка прав
    _, _, has_permission = _check_user_permissions(
        request.user, can_manage_competition_results
    )
    if not has_permission:
        return JsonResponse(
            {
                "success": False,
                "error": "Нет прав для выполнения этого действия",
            }
        )

    # Получаем результат с проверкой доступа по компании
    result = get_object_or_404(
        CustumerCompetitionResult.objects.select_related("competition__owner"),
        id=result_id,
        competition__owner__company=request.user.company,
    )

    result.delete()
    return JsonResponse({"success": True})
