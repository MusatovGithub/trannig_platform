from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from custumer.models import (
    Custumer,
    CustumerRepresentatives,
    TypeRepresentatives,
)


@login_required
def custumer_representatives_all(request, pk):
    user = request.user
    context = {}
    context["cutumer"] = get_object_or_404(Custumer, id=pk)
    context["objects_list"] = CustumerRepresentatives.objects.filter(
        custumer=context["cutumer"]
    )
    if user.groups.filter(name="admin").exists():
        template = "customer/representatives/index.html"
    elif user.groups.filter(name="assistant").exists():
        template = "customer/representatives/assistant/index.html"
    else:
        logout(request)
        return render(request, "page_404.html")

    return render(request, template, context)


@login_required
def custumer_representatives_create(request, pk):
    user = request.user
    custumer = get_object_or_404(Custumer, id=pk)
    objects_list = TypeRepresentatives.objects.all()

    # **Rolga qarab template tanlash**
    if user.groups.filter(name="admin").exists():
        template = "customer/representatives/create.html"
    elif user.groups.filter(name="assistant").exists():
        template = "customer/representatives/assistant/create.html"
    else:
        logout(request)
        return render(request, "page_404.html")

    if request.method == "POST":
        type_id = request.POST.get("type")
        full_name = request.POST.get("full_name")
        phone = request.POST.get("phone")
        work = request.POST.get("work")

        if not type_id or not full_name or not phone:
            context = {
                "cutumer": custumer,
                "objects_list": objects_list,
                "error": "Все обязательные поля должны быть заполнены.",
                "form_data": {
                    "full_name": full_name,
                    "phone": phone,
                    "work": work,
                },
            }
            return render(request, template, context)

        try:
            type_obj = TypeRepresentatives.objects.get(id=type_id)
        except TypeRepresentatives.DoesNotExist:
            context = {
                "cutumer": custumer,
                "objects_list": objects_list,
                "error": "Указанный тип родства не найден.",
                "form_data": {
                    "full_name": full_name,
                    "phone": phone,
                    "work": work,
                },
            }
            return render(request, template, context)

        CustumerRepresentatives.objects.create(
            type=type_obj,
            full_name=full_name,
            phone=phone,
            work=work,
            custumer=custumer,
        )
        return redirect("customer:custumer_representatives_all", pk=pk)

    return render(
        request, template, {"cutumer": custumer, "objects_list": objects_list}
    )


@login_required
def custumer_representatives_delete(request, customer_id, representative_id):
    # Obyektlarni olish
    custumer = get_object_or_404(Custumer, id=customer_id)
    representative = get_object_or_404(
        CustumerRepresentatives, id=representative_id, custumer=custumer
    )
    representative.delete()
    return redirect("customer:custumer_representatives_all", customer_id)
