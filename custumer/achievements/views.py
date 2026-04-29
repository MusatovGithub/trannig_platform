from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import redirect, render

from achievements.models import Achievement
from custumer.models import Custumer, PointsHistory
from custumer.schemas import ReasonTextChoices
from supervisor.views import is_client


@login_required
@transaction.atomic
def assign_achievements(request, pk):
    customer = (
        Custumer.objects.filter(id=pk, company=request.user.company)
        .prefetch_related("achievements")
        .first()
    )
    if not customer:
        return render(request, "page_404.html")
    # Только свои достижения
    achievements = Achievement.objects.filter(owner=request.user)
    if request.method == "POST":
        achievement_ids = set(map(int, request.POST.getlist("achievements")))
        old_achievements_ids = set(
            customer.achievements.values_list("id", flat=True)
        )

        new_achievements_ids = achievement_ids - old_achievements_ids
        removed_achievements_ids = old_achievements_ids - achievement_ids

        achievement_history = []

        # Обрабатываем новые достижения
        if new_achievements_ids:
            new_achievements = Achievement.objects.filter(
                id__in=new_achievements_ids
            )
            total_new_points = sum(
                achievement.points for achievement in new_achievements
            )
            customer.balance += total_new_points

            # Создаем записи для новых достижений
            for achievement in new_achievements:
                achievement_history.append(
                    PointsHistory(
                        custumer=customer,
                        points=achievement.points,
                        reason=ReasonTextChoices.ACHIEVEMENT,
                        description=f"Достижение: {achievement.name}",
                        achievement=achievement,
                        awarded_by=request.user,
                    )
                )

        # Обрабатываем удаляемые достижения
        if removed_achievements_ids:
            removed_achievements = Achievement.objects.filter(
                id__in=removed_achievements_ids
            )
            total_removed_points = sum(
                achievement.points for achievement in removed_achievements
            )

            # Проверяем, достаточно ли баллов для списания
            if customer.balance >= total_removed_points:
                customer.balance -= total_removed_points

                # Создаем записи для удаляемых достижений
                # (отрицательные баллы)
                for achievement in removed_achievements:
                    achievement_history.append(
                        PointsHistory(
                            custumer=customer,
                            points=-achievement.points,  # Отрицательные баллы
                            reason=ReasonTextChoices.ACHIEVEMENT,
                            description=(
                                f"Отмена достижения: {achievement.name}"
                            ),
                            achievement=achievement,
                            awarded_by=request.user,
                        )
                    )
            else:
                # Если недостаточно баллов, не удаляем достижения
                # Можно добавить сообщение об ошибке
                pass

        PointsHistory.objects.bulk_create(achievement_history)
        customer.achievements.set(achievement_ids)
        customer.save()
        return redirect("customer:custumer_detaile", pk=customer.id)
    return render(
        request,
        "customer/achievements/assign_achievements.html",
        {
            "customer": customer,
            "achievements": achievements,
        },
    )


@login_required
@user_passes_test(is_client, login_url="logout_user")
def get_my_achievements(request):
    user = request.user
    custumer = Custumer.objects.get(user=user)
    tag = request.GET.get("tag", "")
    # active, inactive, all
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("search", "")

    all_achievements_qs = Achievement.objects.filter(
        owner__company=user.company
    )

    # Фильтр по тегу
    if tag in {
        "basic",
        "advanced",
        "pro",
        "water_element",
        "swimming_skills",
        "champion_path",
        "team_captain",
        "land_champion",
        "media_champion",
        "challenge_master",
    }:
        all_achievements_qs = all_achievements_qs.filter(tag=tag)

    # Поиск по названию
    if search_query:
        all_achievements_qs = all_achievements_qs.filter(
            name__icontains=search_query
        )

    all_achievements_qs = all_achievements_qs.order_by("-id")

    active_achievements_ids = set(
        custumer.achievements.values_list("id", flat=True)
    )

    # Разделяем на активные и неактивные
    active_achievements = []
    inactive_achievements = []

    for achievement in all_achievements_qs:
        if achievement.id in active_achievements_ids:
            active_achievements.append(achievement)
        else:
            inactive_achievements.append(achievement)

    # Сортируем каждую группу по ID
    active_achievements.sort(key=lambda a: -a.id)
    inactive_achievements.sort(key=lambda a: -a.id)

    # Применяем фильтр по статусу
    if status_filter == "active":
        inactive_achievements = []
    elif status_filter == "inactive":
        active_achievements = []

    # Передаем отдельные списки в контекст
    context = {
        "active_achievements": active_achievements,
        "inactive_achievements": inactive_achievements,
        "active_achievements_ids": active_achievements_ids,
        "current_tag": tag,
        "current_status": status_filter,
        "search_query": search_query,
    }

    # Для AJAX-запроса возвращаем только HTML достижений
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(
            request,
            "customer/cabinet/_my_achievements_list.html",
            context,
        )

    return render(request, "customer/cabinet/my_achievements.html", context)
