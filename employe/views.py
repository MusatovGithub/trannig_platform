import secrets
import string

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from authen.models import CustomUser, Gender
from authen.temp_password import set_temporary_password_state
from base.cache_utils import get_cached_genders
from base.email_utils import prettify_email_address
from base.tasks import send_email_to_user
from employe.models import Employe, EmployeRoll


@login_required
def employe_list(request):
    user = request.user
    query = request.GET.get("search", "")
    employe_list = Employe.objects.select_related("roll").filter(
        company=request.user.company
    )

    if query:
        employe_list = employe_list.filter(
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(user__email__icontains=query)
            | Q(roll__name__icontains=query)
        )

    context = {
        "employe_list": employe_list.order_by("-id"),
        "search_query": query,
    }
    if user.groups.filter(name="admin").exists():
        template = "employe/index.html"
    elif user.groups.filter(name="assistant").exists() and any(
        permission.name == "Может просматривать сотрудников"
        for item in user.user_id.all()
        for permission in item.roll.perm.all()
    ):
        template = "employe/assistent/index.html"
    else:
        logout(request)
        return render(request, "page_404.html")
    return render(request, template, context)


@login_required
def employe_create(request):
    user = request.user

    # Default template
    template = (
        "employe/create.html"
        if user.groups.filter(name="admin").exists()
        else "employe/assistent/create.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может добавлять сотрудников"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        context = {}
        context["gender"] = get_cached_genders()
        context["roll"] = EmployeRoll.objects.filter(
            company=request.user.company
        ).order_by("-id")

        if request.method == "POST":
            full_name = request.POST.get("full_name")
            phone = request.POST.get("phone")
            decription = request.POST.get("decription")
            roll_id = request.POST.get("roll")
            gender_id = request.POST.get("gender")

            if not full_name or not phone or not gender_id or not roll_id:
                context["error"] = "Заполните все обязательные поля!"
                return render(request, template, context)

            gender_obj = get_object_or_404(Gender, id=gender_id)
            rol_obj = get_object_or_404(EmployeRoll, id=roll_id)

            if Employe.objects.filter(Q(phone=phone)).exists():
                context["error"] = "Номер телефона уже зарегистрирован."
                return render(request, template, context)

            Employe.objects.create(
                full_name=full_name,
                phone=phone,
                decription=decription,
                gender=gender_obj,
                roll=rol_obj,
                company=request.user.company,
                owner=request.user,
            )
            return redirect("employe:employe_list")
        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def employe_update(request, pk):
    user = request.user

    # Default template
    template = (
        "employe/update.html"
        if user.groups.filter(name="admin").exists()
        else "employe/assistent/update.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может редактировать сотрудников"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        context = {}
        context["employe"] = get_object_or_404(Employe, id=pk)
        context["gender"] = get_cached_genders()
        context["roll"] = EmployeRoll.objects.filter(
            company=request.user.company
        ).order_by("-id")

        if request.method == "POST":
            full_name = request.POST.get("full_name")
            phone = request.POST.get("phone")
            decription = request.POST.get("decription")
            gender_id = request.POST.get("gender")
            roll_id = request.POST.get("roll")

            if not full_name or not phone or not gender_id or not roll_id:
                context["error"] = "Заполните все обязательные поля!"
                return render(request, template, context)

            if Employe.objects.filter(Q(phone=phone) & ~Q(id=pk)).exists():
                context["error"] = "Номер телефона уже зарегистрирован."
                return render(request, template, context)

            gender_obj = get_object_or_404(Gender, id=gender_id)
            rol_obj = get_object_or_404(EmployeRoll, id=roll_id)

            context["employe"].full_name = full_name
            context["employe"].phone = phone
            context["employe"].decription = decription
            context["employe"].gender_id = gender_obj
            context["employe"].roll_id = rol_obj
            context["employe"].save()

            return redirect("employe:employe_list")

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def employe_delete(request, pk):
    user = request.user
    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может удалять сотрудников"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        try:
            employe = Employe.objects.get(id=pk)

            if employe.user:
                employe.user.delete()
                employe.user = None
                employe.is_send = False
                employe.save()

            return redirect("employe:employe_list")
        except Employe.DoesNotExist:
            return redirect("employe:employe_list")
    logout(request)
    return render(request, "page_404.html")


@login_required
def employe_send_message(request, pk):
    user = request.user

    # Default template
    template = (
        "employe/send_message.html"
        if user.groups.filter(name="admin").exists()
        else "employe/assistent/send_message.html"
    )

    if user.groups.filter(name="admin").exists() or (
        user.groups.filter(name="assistant").exists()
        and any(
            permission.name == "Может добавлять сотрудников"
            for item in user.user_id.all()
            for permission in item.roll.perm.all()
        )
    ):
        context = {}
        context["employe"] = get_object_or_404(Employe, id=pk)

        if request.method == "POST":
            email = request.POST.get("email")
            if not email:
                context["error"] = "Требуется адрес электронной почты."
                return render(request, template, context)

            # Валидация email
            if "@" not in email or "." not in email.split("@")[-1]:
                context["error"] = (
                    "Введите корректный адрес электронной почты."
                )
                return render(request, template, context)

            # Проверяем, не зарегистрирован ли уже этот email
            if CustomUser.objects.filter(Q(email=email)).exists():
                context["error"] = "E-mail уже зарегистрирован."
                return render(request, template, context)

            # Проверяем, есть ли уже пользователь у этого сотрудника
            if context["employe"].user:
                context["error"] = (
                    "У этого сотрудника уже есть учетная запись."
                )
                return render(request, template, context)

            alphabet = (
                string.ascii_letters + string.digits + string.punctuation
            )
            password = "".join(secrets.choice(alphabet) for _ in range(8))

            subject = "Временный доступ к платформе"
            login_link = request.build_absolute_uri(reverse("sign_in"))
            password_change_link = request.build_absolute_uri(
                reverse("force_password_change")
            )
            message = (
                f"Здравствуйте, {context['employe'].full_name}!\n\n"
                "Для вас создан доступ в тренировочную платформу.\n"
                f"Логин: {email}\n"
                f"Временный пароль: {password}\n\n"
                "Что нужно сделать:\n"
                "1. Войти в систему по ссылке ниже.\n"
                "2. Сразу сменить временный пароль на постоянный.\n\n"
                f"Вход в систему: {login_link}\n"
                f"Смена пароля после входа: {password_change_link}\n\n"
                "Если вы не запрашивали доступ, проигнорируйте это письмо."
            )
            html_message = render_to_string(
                "emails/temporary_access.html",
                {
                    "recipient_name": context["employe"].full_name,
                    "login_email": email,
                    "temporary_password": password,
                    "login_link": login_link,
                    "password_change_link": password_change_link,
                    "support_email": prettify_email_address(
                        settings.EMAIL_REPLY_TO
                    ),
                },
            )
            extra_headers = {
                "Reply-To": settings.EMAIL_REPLY_TO,
                "List-Unsubscribe": (
                    f"<mailto:{settings.EMAIL_UNSUBSCRIBE_EMAIL}"
                    "?subject=unsubscribe>"
                ),
            }
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [email]

            try:
                # Создаем пользователя в транзакции
                with transaction.atomic():
                    # Создаем пользователя
                    user = CustomUser.objects.create(
                        first_name=context["employe"].full_name,
                        username=email,
                        email=email,
                        company=request.user.company,
                        password=make_password(password),
                        phone=context["employe"].phone,
                    )

                    # Добавляем в группу assistant
                    group, created = Group.objects.get_or_create(
                        name="assistant"
                    )
                    user.groups.add(group)

                    # Обновляем данные сотрудника
                    context["employe"].user = user
                    context["employe"].is_send = True
                    context["employe"].save()
                    set_temporary_password_state(user)

                    transaction.on_commit(
                        lambda: send_email_to_user.delay(
                            subject,
                            message,
                            from_email,
                            recipient_list,
                            html_message,
                            extra_headers,
                        )
                    )
                return redirect("employe:employe_list")

            except Exception as e:
                # Более детальная обработка ошибок
                error_message = "Произошла ошибка при создании учетной записи."

                if "email" in str(e).lower():
                    error_message = (
                        "Ошибка с адресом электронной почты. "
                        "Проверьте корректность введенного email."
                    )
                elif "phone" in str(e).lower():
                    error_message = (
                        "Ошибка с номером телефона. "
                        "Проверьте корректность номера телефона сотрудника."
                    )
                elif "unique" in str(e).lower():
                    error_message = (
                        "Пользователь с такими данными уже существует "
                        "в системе."
                    )
                else:
                    error_message = (
                        f"Ошибка при создании учетной записи: {str(e)}"
                    )

                context["error"] = error_message
                return render(request, template, context)
        return render(request, template, context)
    return render(request, "page_404.html")
