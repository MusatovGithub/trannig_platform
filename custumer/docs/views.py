from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from custumer.models import Custumer, CustumerDocs


@login_required
def custumer_docs_all(request, pk):
    user = request.user
    custumer = get_object_or_404(Custumer, id=pk)
    docs = CustumerDocs.objects.filter(custumer=custumer)

    # **Rolga qarab template tanlash**
    if user.groups.filter(name="admin").exists():
        template = "customer/docs/index.html"
    elif user.groups.filter(name="assistant").exists():
        template = "customer/docs/index2.html"
    else:
        logout(request)
        return render(request, "page_404.html")

    if request.method == "POST":
        name = request.POST.get("name")
        file = request.FILES.get("file")

        if not name or not file:
            context = {
                "cutumer": custumer,
                "docs": docs,
                "error": "Название и файл обязательны для заполнения.",
            }
            return render(request, template, context)

        CustumerDocs.objects.create(custumer=custumer, name=name, files=file)
        return redirect("customer:custumer_docs_all", pk=custumer.id)

    return render(request, template, {"cutumer": custumer, "docs": docs})


@login_required
def custumer_dos_delet(request, custumer_id, doc_id):
    custumer = get_object_or_404(Custumer, id=custumer_id)
    doc = get_object_or_404(CustumerDocs, id=doc_id)
    doc.delete()
    return redirect("customer:custumer_docs_all", pk=custumer.id)
