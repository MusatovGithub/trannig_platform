from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from base.permissions import admin_or_assistant_required, admin_required
from news.models import News


@admin_required
def news_create(request):
    """Создание новости."""
    if request.method == "POST":
        title = request.POST.get("title")
        descriptions = request.POST.get("descriptions")
        image = request.FILES.get("image")
        status = request.POST.get("status")
        News.objects.create(
            title=title,
            descriptions=descriptions,
            image=image,
            owner=request.user,
            status=status,
        )
        return redirect("news:news_list")
    status_choices = News._meta.get_field("status").choices
    return render(
        request, "news/create.html", {"status_choices": status_choices}
    )


@admin_or_assistant_required
def news_list(request):
    """Вывод списка новостей."""
    page = int(request.GET.get("page", 1))
    per_page = 8
    news = News.objects.filter(owner=request.user).order_by("-created_at")
    paginator = Paginator(news, per_page)
    page_obj = paginator.get_page(page)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "news/_news_list.html", {"page_obj": page_obj})

    return render(request, "news/list.html", {"page_obj": page_obj})


@admin_required
def news_update(request, pk):
    """Обновление новости."""
    news_item = get_object_or_404(News, pk=pk, owner=request.user)
    if request.method == "POST":
        news_item.title = request.POST.get("title")
        news_item.descriptions = request.POST.get("descriptions")
        news_item.status = request.POST.get("status")
        if request.FILES.get("image"):
            news_item.image = request.FILES.get("image")
        news_item.save()
        return redirect("news:news_list")
    status_choices = News._meta.get_field("status").choices
    return render(
        request,
        "news/update.html",
        {"news_item": news_item, "status_choices": status_choices},
    )


@admin_required
def news_delete(request, pk):
    """Удаление новости."""
    news_item = get_object_or_404(News, pk=pk, owner=request.user)
    if request.method == "POST":
        news_item.delete()
        return redirect("news:news_list")
    return render(
        request, "news/delete_confirm.html", {"news_item": news_item}
    )
