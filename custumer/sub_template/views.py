from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from custumer.models import SubscriptionTemplate


@login_required
def subscription_template_all(request):
    user = request.user
    context = {}
    context["objects_list"] = SubscriptionTemplate.objects.filter(
        company=request.user.company
    )

    if user.groups.filter(name="admin").exists():
        template = "subscriptions_temp/index.html"
    elif user.groups.filter(name="assistant").exists() and any(
        permission.name == "Может добавлять Абонементы"
        for item in user.user_id.all()
        for permission in item.roll.perm.all()
    ):
        template = "subscriptions_temp/assistent/index.html"
    else:
        logout(request)
        return render(request, "page_404.html")
    return render(request, template, context)


@login_required
def subscription_template_add(request):
    user = request.user

    # Default template
    template = (
        "subscriptions_temp/create.html"
        if user.groups.filter(name="admin").exists()
        else "subscriptions_temp/assistent/create.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может добавлять Абонементы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        context = {}

        if request.method == "POST":
            name = request.POST.get("name")
            price = request.POST.get("price")
            expired = request.POST.get("expired")
            duration_type = request.POST.get("duration_type")
            number = request.POST.get("number")
            unlimited = "unlimited" in request.POST

            is_day = duration_type == "day"
            is_week = duration_type == "week"
            is_month = duration_type == "month"

            if not name or not price or not expired:
                context["error"] = "Заполните все поля!"
                return render(request, template, context)

            SubscriptionTemplate.objects.create(
                name=name,
                price=price,
                expired=expired,
                is_day=is_day,
                is_week=is_week,
                is_month=is_month,
                number_classes=int(number) if number else None,
                unlimited=unlimited,
                company=request.user.company,
            )
            return redirect("customer:subscription_template_all")

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def subscription_template_update(request, pk):
    user = request.user

    # Default template
    template = (
        "subscriptions_temp/update.html"
        if user.groups.filter(name="admin").exists()
        else "subscriptions_temp/assistent/update.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может добавлять Абонементы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        context = {}
        context["objects"] = get_object_or_404(SubscriptionTemplate, id=pk)

        if request.method == "POST":
            name = request.POST.get("name")
            price = request.POST.get("price")
            expired = request.POST.get("expired")
            duration_type = request.POST.get("duration_type")
            number = request.POST.get("number")
            unlimited = "unlimited" in request.POST

            is_day = duration_type == "day"
            is_week = duration_type == "week"
            is_month = duration_type == "month"

            if not name or not price or not expired:
                context["error"] = "Заполните все поля!"
                return render(request, template, context)

            context["objects"].name = name
            context["objects"].price = price
            context["objects"].expired = expired
            context["objects"].is_day = is_day
            context["objects"].is_week = is_week
            context["objects"].is_month = is_month
            context["objects"].number_classes = number
            context["objects"].unlimited = unlimited
            context["objects"].save()
            return redirect("customer:subscription_template_all")

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def subscription_template_delete(request, pk):
    user = request.user
    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может добавлять Абонементы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        tmp = get_object_or_404(SubscriptionTemplate, id=pk)
        tmp.delete()
        return redirect("customer:subscription_template_all")
    logout(request)
    return render(request, "page_404.html")
