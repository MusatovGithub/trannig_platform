from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from custumer.models import Cashier


@login_required
def cashier_list(request):
    user = request.user
    context = {}
    context["objects_list"] = Cashier.objects.filter(
        company=request.user.company
    )

    if user.groups.filter(name="admin").exists():
        template = "cashier/index.html"
    elif user.groups.filter(name="assistant").exists() and any(
        permission.name == "Может просматривать кассы"
        for item in user.user_id.all()
        for permission in item.roll.perm.all()
    ):
        template = "cashier/assistent/index.html"
    else:
        logout(request)
        return render(request, "page_404.html")
    return render(request, template, context)


@login_required
def cashier_create(request):
    user = request.user

    # Default template
    template = (
        "cashier/create.html"
        if user.groups.filter(name="admin").exists()
        else "cashier/assistent/create.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может создавать кассы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        context = {}

        if request.method == "POST":
            name = request.POST.get("name")
            description = request.POST.get("description")

            if not name:
                context["error"] = "Название обязательно!"
                return render(request, template, context)

            cashier = Cashier(
                name=name,
                description=description,
                company=request.user.company,
                owner=request.user,
            )
            cashier.save()
            return redirect("customer:cashier_list")

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def cashier_update(request, pk):
    user = request.user

    # Default template
    template = (
        "cashier/update.html"
        if user.groups.filter(name="admin").exists()
        else "cashier/assistent/update.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может изменять кассы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        context = {}
        context["cashier"] = get_object_or_404(Cashier, id=pk)

        if request.method == "POST":
            name = request.POST.get("name")
            description = request.POST.get("description")

            if not name:
                context["error"] = "Название обязательно!"
                return render(request, template, context)

            context["cashier"].name = name
            context["cashier"].description = description
            context["cashier"].save()
            return redirect("customer:cashier_list")
        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def cashier_delete(request, pk):
    user = request.user
    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может удалять кассы"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        cashier = get_object_or_404(Cashier, id=pk)
        cashier.delete()
        return redirect("customer:cashier_list")
    logout(request)
    return render(request, "page_404.html")
