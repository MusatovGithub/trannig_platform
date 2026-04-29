from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from achievements.models import Achievement
from base.permissions import admin_or_assistant_required, admin_required


@admin_or_assistant_required
def achievement_list(request):
    """Вывод списка достижений."""
    page = int(request.GET.get("page", 1))
    per_page = 8
    tag = request.GET.get("tag", "")
    achievements = Achievement.objects.filter(owner=request.user)
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
        achievements = achievements.filter(tag=tag)
    achievements = achievements.order_by("-id")
    paginator = Paginator(achievements, per_page)
    page_obj = paginator.get_page(page)

    # Для AJAX-запроса возвращаем только HTML достижений
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(
            request,
            "achievements/_achievements_list.html",
            {"page_obj": page_obj, "current_tag": tag},
        )

    # Для обычного запроса — всю страницу
    return render(
        request,
        "achievements/index.html",
        {"page_obj": page_obj, "current_tag": tag},
    )


@admin_required
def achievement_create(request):
    """Создание достижения."""
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")
        tag = request.POST.get("tag")
        points = request.POST.get("points")
        Achievement.objects.create(
            name=name,
            description=description,
            image=image,
            owner=request.user,
            tag=tag,
            points=points,
        )
        return redirect("achievements:achievement_list")
    tag_choices = Achievement._meta.get_field("tag").choices
    return render(
        request, "achievements/create.html", {"tag_choices": tag_choices}
    )


@admin_required
def achievement_update(request, pk):
    """Обновление достижения."""
    achievement = Achievement.objects.get(id=pk)
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")
        tag = request.POST.get("tag")
        points = request.POST.get("points")
        achievement.name = name
        achievement.description = description
        achievement.tag = tag
        achievement.points = points
        if image:
            achievement.image = image
        achievement.save()
        return redirect("achievements:achievement_list")
    tag_choices = Achievement._meta.get_field("tag").choices
    return render(
        request,
        "achievements/update.html",
        {"achievement": achievement, "tag_choices": tag_choices},
    )
