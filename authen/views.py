from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string

from authen.models import Company, CustomUser, UserProfile
from authen.temp_password import (
    clear_temporary_password_state,
    is_temporary_password_expired,
)


def _redirect_by_user_group(user):
    if user.groups.filter(name="admin").exists():
        return redirect("supervisor:cabinet")
    if user.groups.filter(name="assistant").exists():
        return redirect("supervisor:home_epmloye")
    if user.groups.filter(name="client").exists():
        return redirect("supervisor:home_client")
    return None


def sign_in(request):
    context = {}
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        if not username or not password:
            context["error"] = "Логин или пароль пуст !"
            return render(request, "authen/login.html", context)
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.must_change_password:
                if is_temporary_password_expired(user):
                    clear_temporary_password_state(user)
                    logout(request)
                    context["error"] = (
                        "Срок действия временного пароля истек. "
                        "Запросите новый доступ у администратора."
                    )
                    return render(request, "authen/login.html", context)
                return redirect("force_password_change")

            group_redirect = _redirect_by_user_group(user)
            if group_redirect:
                return group_redirect
            else:
                context["error"] = "Доступ к этой системе запрещен !"
                return render(request, "authen/login.html", context)
        else:
            context["error"] = "неверный логин или пароль !"
    return render(request, "authen/login.html", context)


def sign_up(request):
    context = {}
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        company = request.POST.get("company")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")

        # Bo'sh maydonlarni tekshirish
        if not all([name, company, email, phone, password, password2]):
            context["error"] = "Заполните информацию!"
            return render(request, "authen/register.html", context)

        # Parolni tasdiqlash
        if password != password2:
            context["error"] = "Пароли не совпадают. Попробуйте еще раз."
            return render(request, "authen/register.html", context)

        # Email va telefon mavjudligini tekshirish
        if CustomUser.objects.filter(email=email).exists():
            context["error"] = (
                "Этот e-mail уже занят. Пожалуйста, выберите другой."
            )
            return render(request, "authen/register.html", context)
        if CustomUser.objects.filter(phone=phone).exists():
            context["error"] = (
                "Этот телефон уже занят. Пожалуйста, выберите другой."
            )
            return render(request, "authen/register.html", context)
        company, created = Company.objects.get_or_create(name=company)
        # Foydalanuvchini yaratish
        try:
            user = CustomUser.objects.create(
                first_name=name,
                username=email,
                email=email,
                phone=phone,
                company=company,
                password=make_password(password),  # Parolni shifrlash
            )
            admin_group, created = Group.objects.get_or_create(name="admin")
            user.groups.add(admin_group)
            context["success"] = "Регистрация прошла успешно!"
            return redirect("sign_in")  # Login sahifasiga yo'naltirish
        except Exception as e:
            context["error"] = f"Ошибка при регистрации: {e}"
            return render(request, "authen/register.html", context)

    return render(request, "authen/register.html", context)


@login_required
def logout_user(request):
    logout(request)
    return redirect("/")


@login_required
def change_profile_assistent(request):
    context = {}
    context["user_change"] = get_object_or_404(CustomUser, id=request.user.id)
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        avatar = request.FILES.get("avatar")
        if avatar:
            context["user_change"].avatar = avatar
            context["user_change"].save(update_fields=["avatar"])
        if not name or not phone or not email:
            context["error"] = "Заполните информацию !"
            return render(
                request, "authen/assistent/profile_change.html", context
            )

        if (
            CustomUser.objects.exclude(id=context["user_change"].id)
            .filter(phone=phone)
            .exists()
        ):
            context["error"] = (
                "Этот телефон уже занят. Пожалуйста, выберите другой."
            )
            return render(
                request, "authen/assistent/profile_change.html", context
            )

        if (
            CustomUser.objects.exclude(id=context["user_change"].id)
            .filter(email=email)
            .exists()
        ):
            context["error"] = (
                "Этот e-mail уже занят. Пожалуйста, выберите другой."
            )
            return render(
                request, "authen/assistent/profile_change.html", context
            )

        context["user_change"].username = email
        context["user_change"].first_name = name
        context["user_change"].phone = phone
        context["user_change"].email = email
        context["user_change"].save()

        return redirect("supervisor:home_epmloye")
    return render(request, "authen/assistent/profile_change.html", context)


@login_required
def change_profile_client(request):
    context = {}
    context["user_change"] = get_object_or_404(CustomUser, id=request.user.id)
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        avatar = request.FILES.get("avatar")
        if avatar:
            context["user_change"].avatar = avatar
            context["user_change"].save(update_fields=["avatar"])
        if not name or not phone or not email:
            context["error"] = "Заполните информацию !"
            return render(
                request, "authen/client/change_profile.html", context
            )
        if (
            CustomUser.objects.exclude(id=context["user_change"].id)
            .filter(phone=phone)
            .exists()
        ):
            context["error"] = (
                "Этот телефон уже занят. Пожалуйста, выберите другой."
            )
            return render(
                request, "authen/client/change_profile.html", context
            )
        if (
            CustomUser.objects.exclude(id=context["user_change"].id)
            .filter(email=email)
            .exists()
        ):
            context["error"] = (
                "Этот e-mail уже занят. Пожалуйста, выберите другой."
            )
            return render(
                request, "authen/client/change_profile.html", context
            )
        # Обновляем данные пользователя - синхронизация с Custumer
        # произойдет автоматически
        context["user_change"].username = email
        context["user_change"].first_name = name
        context["user_change"].phone = phone
        context["user_change"].email = email
        context["user_change"].save()
        return redirect("supervisor:home_client")
    return render(request, "authen/client/change_profile.html", context)


@login_required
def change_password_client(request):
    context = {}
    context["user_change"] = get_object_or_404(CustomUser, id=request.user.id)
    if request.method == "POST":
        password = request.POST.get("password")
        password2 = request.POST.get("password2")
        if password != password2:
            context["error"] = "Пароли не совпадают. Попробуйте еще раз."
            return render(
                request, "authen/client/change_password.html", context
            )
        context["user_change"].set_password(password)
        context["user_change"].save()
        update_session_auth_hash(request, context["user_change"])
        clear_temporary_password_state(context["user_change"])
        return redirect("supervisor:home_client")
    return render(request, "authen/client/change_password.html", context)


@login_required
def change_profile(request):
    context = {}
    context["user_change"] = get_object_or_404(CustomUser, id=request.user.id)
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        company = request.POST.get("company")
        avatar = request.FILES.get("avatar")
        if avatar:
            context["user_change"].avatar = avatar
            context["user_change"].save(update_fields=["avatar"])
        if not name or not company or not phone or not email:
            context["error"] = "Заполните информацию !"
            return render(request, "authen/admin/profile_change.html", context)

        if (
            CustomUser.objects.exclude(id=context["user_change"].id)
            .filter(phone=phone)
            .exists()
        ):
            context["error"] = (
                "Этот телефон уже занят. Пожалуйста, выберите другой."
            )
            return render(request, "authen/admin/profile_change.html", context)

        if (
            CustomUser.objects.exclude(id=context["user_change"].id)
            .filter(email=email)
            .exists()
        ):
            context["error"] = (
                "Этот e-mail уже занят. Пожалуйста, выберите другой."
            )
            return render(request, "authen/admin/profile_change.html", context)

        context["user_change"].username = email
        context["user_change"].first_name = name

        context["user_change"].phone = phone
        context["user_change"].email = email

        context["user_change"].save()

        if (
            context["user_change"].company
            and context["user_change"].company.name != company
        ):
            context["user_change"].company.name = company
            context["user_change"].company.save(update_fields=["name"])
        return redirect("supervisor:cabinet")
    return render(request, "authen/admin/profile_change.html", context)


@login_required
def change_password(request):
    context = {}
    user_instance = get_object_or_404(CustomUser, id=request.user.id)

    if user_instance.groups.filter(name="admin").exists():
        template_name = "authen/admin/change_password.html"
    elif user_instance.groups.filter(name="assistant").exists():
        template_name = "authen/assistent/change_password.html"
    else:
        template_name = "page_404.html"
    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        if not current_password or not new_password or not confirm_password:
            context["error"] = "Заполните информацию !"
            return render(request, template_name, context)

        if not check_password(current_password, user_instance.password):
            context["error"] = "Текущий пароль введен неверно!"
            return render(request, template_name, context)

        if new_password != confirm_password:
            context["error"] = "Новый пароль и его подтверждение не совпадают!"
            return render(request, template_name, context)
        user_instance.set_password(new_password)
        user_instance.save()
        clear_temporary_password_state(user_instance)
        return redirect("sign_in")
    return render(request, template_name, context)


def forget_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        if not email:
            error = "Заполните информацию !"
            return render(
                request, "authen/forget_password.html", {"error": error}
            )
        try:
            user = CustomUser.objects.get(email=email)
            user_profile, created = UserProfile.objects.get_or_create(
                user=user
            )
            reset_token = get_random_string(length=32)
            user.userprofile.reset_token = reset_token
            user.userprofile.save()
            # Используем динамический URL вместо хардкода
            reset_link = request.build_absolute_uri(
                f"/reset/password/{reset_token}/"
            )
            subject = "Password Reset"
            message = render_to_string(
                "authen/password_email.txt", {"reset_link": reset_link}
            )
            from_email = "istamovibrohim8@gmail.com"
            recipient_list = [email]
            send_mail(subject, message, from_email, recipient_list)
            return redirect("/")
        except CustomUser.DoesNotExist:
            # Не раскрываем информацию о существовании пользователя
            # для безопасности (защита от перебора email)
            return redirect("/")
    return render(request, "authen/forget_password.html")


def reset_passwords(request, reset_token):
    user_profile = get_object_or_404(UserProfile, reset_token=reset_token)
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not new_password or not confirm_password:
            error = "Заполните информацию !"
            return render(
                request,
                "authen/password_reset.html",
                {"reset_token": reset_token, "error": error},
            )

        if new_password != confirm_password:
            error = "Новый пароль и его подтверждение не совпадают!"
            return render(
                request,
                "authen/password_reset.html",
                {"reset_token": reset_token, "error": error},
            )
        user = user_profile.user
        user.set_password(new_password)
        user.save()
        clear_temporary_password_state(user)
        user_profile.reset_token = None
        user_profile.save()
        return redirect("/")
    return render(
        request, "authen/password_reset.html", {"reset_token": reset_token}
    )


@login_required
def force_password_change(request):
    if not request.user.must_change_password:
        group_redirect = _redirect_by_user_group(request.user)
        if group_redirect:
            return group_redirect
        return redirect("sign_in")
    if is_temporary_password_expired(request.user):
        clear_temporary_password_state(request.user)
        logout(request)
        return render(
            request,
            "authen/login.html",
            {
                "error": (
                    "Срок действия временного пароля истек. "
                    "Запросите новый доступ у администратора."
                )
            },
        )

    context = {"error": None}
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not new_password or not confirm_password:
            context["error"] = "Заполните информацию !"
            return render(request, "authen/password_reset.html", context)

        if new_password != confirm_password:
            context["error"] = "Новый пароль и его подтверждение не совпадают!"
            return render(request, "authen/password_reset.html", context)

        if len(new_password) < 8:
            context["error"] = "Пароль должен содержать минимум 8 символов."
            return render(request, "authen/password_reset.html", context)

        if check_password(new_password, request.user.password):
            context["error"] = "Новый пароль не должен совпадать с временным."
            return render(request, "authen/password_reset.html", context)

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        clear_temporary_password_state(request.user)

        group_redirect = _redirect_by_user_group(request.user)
        if group_redirect:
            return group_redirect
        return redirect("sign_in")

    return render(request, "authen/password_reset.html", context)
