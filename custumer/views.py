import json
import secrets
import string

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from authen.models import CustomUser
from authen.temp_password import set_temporary_password_state
from base.cache_utils import (
    get_cached_company_groups,
    get_cached_genders,
    get_cached_sport_categories,
)
from base.email_utils import prettify_email_address
from base.permissions import admin_required
from base.tasks import send_email_to_user
from custumer.models import Custumer, PointsHistory
from custumer.schemas import ReasonTextChoices
from custumer.services.customer import create_customer, update_customer
from custumer.tasks import sync_customer_attendances
from custumer.utils import get_user_permissions
from employe.models import Employe
from groups_custumer.models import GroupsClass


def _should_return_json(request):
    headers = request.headers
    sec_fetch_mode = headers.get("sec-fetch-mode")
    if sec_fetch_mode and sec_fetch_mode.lower() != "navigate":
        return True
    if headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    accept_header = headers.get("accept", "")
    return "application/json" in accept_header


def _get_customer_list_redirect_url(request):
    return request.session.get("customer_list_return_url") or reverse(
        "customer:customer_list"
    )


def _collect_error_messages(error):
    if isinstance(error, ValidationError):
        if hasattr(error, "messages"):
            return list(error.messages)
        if hasattr(error, "message"):
            return [error.message]
    return [str(error)]


def _set_context_error(context, error):
    messages = _collect_error_messages(error)
    context["errors"] = messages
    context["error"] = messages


def _schedule_attendance_sync(customer_id: int) -> None:
    transaction.on_commit(
        lambda cid=customer_id: sync_customer_attendances.delay(cid)
    )


@login_required
def customer_list(request):
    context = {}
    user = request.user
    company = user.company
    is_admin = user.groups.filter(name="admin").exists()
    is_assistant = user.groups.filter(name="assistant").exists()

    # Получаем разрешения пользователя одним оптимизированным запросом
    user_permissions = get_user_permissions(user)

    # Проверяем разрешения на просмотр клиентов
    can_view_all_custumer = user_permissions["can_view_customers"]
    can_view_own_custumer = user_permissions["can_view_own_customers"]

    # Assistant foydalanuvchini Employe modeliga bog‘lash
    employe_instance = None
    if is_assistant:
        try:
            employe_instance = Employe.objects.get(user=user)
        except Employe.DoesNotExist:
            employe_instance = None

    search_query = request.GET.get("search", "")
    group_filter = request.GET.get("group", "")
    gender_filter = request.GET.get("gender", "")
    birth_year_filter = request.GET.get("birth_year", "")

    page = int(request.GET.get("page", 1))
    per_page = 10

    if is_admin or (
        is_assistant and (can_view_all_custumer or can_view_own_custumer)
    ):
        customers = (
            Custumer.objects.filter(company=company)
            .select_related("user")
            .order_by("full_name")
        )

        # Запоминаем URL списка, чтобы вернуться после действий
        if request.method == "GET":
            request.session["customer_list_return_url"] = (
                request.get_full_path()
            )

        if (
            is_assistant
            and can_view_own_custumer
            and not can_view_all_custumer
            and employe_instance
        ):
            customers = customers.filter(groups__employe_id=employe_instance)

        if search_query:
            customers = customers.filter(
                Q(full_name__icontains=search_query)
                | Q(phone__icontains=search_query)
            )

        if group_filter:
            customers = customers.filter(groups__id=group_filter)

        if gender_filter:
            customers = customers.filter(gender=gender_filter)

        if birth_year_filter:
            customers = customers.filter(birth_date__year=birth_year_filter)

        paginator = Paginator(customers, per_page)
        page_obj = paginator.get_page(page)

        # Admin va Assistant uchun mos shablonni tanlash
        template = (
            "customer/crud/index.html"
            if is_admin
            else "employe/custumer/index.html"
        )

        # Подготавливаем права для шаблона
        user_permissions_dict = {
            "can_add_customers": user_permissions["can_add_customers"],
            "can_edit_customers": user_permissions["can_edit_customers"],
            "can_delete_customers": user_permissions["can_delete_customers"],
        }

        context["groups"] = get_cached_company_groups(company.id)
        context["gender"] = get_cached_genders()
        context["custumer"] = page_obj
        context["user_permissions"] = user_permissions_dict
        context["page_obj"] = page_obj

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def customer_create(request):
    user = request.user

    # Default template
    template = (
        "customer/crud/create.html"
        if user.groups.filter(name="admin").exists()
        else "employe/custumer/create.html"
    )

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_add_customers"]
    ):
        context = {}
        context["gender"] = get_cached_genders()
        context["groups"] = get_cached_company_groups(request.user.company.id)
        context["sport_category"] = get_cached_sport_categories()

        if request.method == "POST":
            payload = {
                "full_name": request.POST.get("full_name"),
                "phone": request.POST.get("phone"),
                "gender": request.POST.get("gender"),
                "birth_date": request.POST.get("birth_date"),
                "address": request.POST.get("address"),
                "contract_number": request.POST.get("contract_number"),
                "contract_type": request.POST.get("contract_type"),
                "start_date": request.POST.get("start_date"),
                "group_ids": request.POST.getlist("group"),
                "sport_rank": request.POST.get("sport_rank"),
            }
            photo = request.FILES.get("photo")

            try:
                with transaction.atomic():
                    result = create_customer(
                        owner=request.user,
                        data=payload,
                        photo=photo,
                    )
                    _schedule_attendance_sync(result.customer.id)

                return redirect("customer:customer_list")
            except ValidationError as error:
                _set_context_error(context, error)
            except Exception as error:  # noqa: BLE001
                _set_context_error(context, error)

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def custumer_update(request, pk):
    context = {}
    context["custumer"] = get_object_or_404(Custumer, id=pk)
    user = request.user

    # Default template
    template = (
        "customer/crud/update.html"
        if user.groups.filter(name="admin").exists()
        else "employe/custumer/update.html"
    )

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_edit_customers"]
    ):
        context["gender"] = get_cached_genders()
        context["groups"] = GroupsClass.objects.filter(owner_id=request.user)
        context["sport_categorys"] = get_cached_sport_categories()

        if request.method == "POST":
            payload = {
                "full_name": request.POST.get("full_name"),
                "phone": request.POST.get("phone"),
                "gender": request.POST.get("gender"),
                "birth_date": request.POST.get("birth_date"),
                "address": request.POST.get("address"),
                "contract_number": request.POST.get("contract_number"),
                "contract_type": request.POST.get("contract_type"),
                "start_date": request.POST.get("start_date"),
                "group_ids": request.POST.getlist("group"),
                "sport_rank": request.POST.get("sport_rank"),
            }
            photo = request.FILES.get("photo")

            try:
                with transaction.atomic():
                    result = update_customer(
                        customer=context["custumer"],
                        owner=request.user,
                        data=payload,
                        photo=photo,
                    )
                    _schedule_attendance_sync(result.customer.id)

                return redirect("customer:customer_list")
            except ValidationError as error:
                _set_context_error(context, error)
            except Exception as error:  # noqa: BLE001
                _set_context_error(context, error)

        return render(request, template, context)
    logout(request)
    return render(request, "page_404.html")


@login_required
def custumer_detaile(request, pk):
    user = request.user
    custumer = get_object_or_404(Custumer, id=pk)

    if user.groups.filter(name="admin").exists():
        template = "customer/crud/detaile.html"
    elif user.groups.filter(name="assistant").exists():
        template = "employe/custumer/detaile.html"
    else:
        logout(request)
        return render(request, "page_404.html")

    return render(request, template, {"custumer": custumer})


@login_required
def cutsumer_delete(request, pk):
    """Удаление клиента (только если приглашение не отправлено)."""
    user = request.user
    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_delete_customers"]
    ):
        custumer = get_object_or_404(Custumer, id=pk)
        # Удалять можно только если приглашение не было отправлено
        if not custumer.is_send:
            custumer.delete()
            messages.success(request, "Клиент успешно удалён")
        else:
            messages.error(
                request,
                "Нельзя удалить клиента с отправленным приглашением. "
                "Используйте 'Закрыть доступ к личному кабинету'",
            )
        redirect_url = _get_customer_list_redirect_url(request)
        if _should_return_json(request):
            return JsonResponse(
                {"success": True, "redirect_url": redirect_url}
            )
        return redirect(redirect_url)
    logout(request)
    return render(request, "page_404.html")


@login_required
def close_cabinet_access(request, pk):
    """Закрытие доступа к личному кабинету (удаление CustomUser)."""
    user = request.user
    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_delete_customers"]
    ):
        custumer = get_object_or_404(Custumer, id=pk)
        # Закрывать доступ можно только если приглашение было отправлено
        if custumer.is_send and custumer.user:
            custumer.user.delete()
            custumer.user = None
            custumer.is_send = False
            custumer.save()
            messages.success(
                request, "Доступ к личному кабинету успешно закрыт"
            )
        else:
            messages.error(
                request,
                "У клиента нет доступа к личному кабинету",
            )
        redirect_url = _get_customer_list_redirect_url(request)
        if _should_return_json(request):
            return JsonResponse(
                {"success": True, "redirect_url": redirect_url}
            )
        return redirect(redirect_url)
    logout(request)
    return render(request, "page_404.html")


@login_required
def send_client_credentials(request, pk):
    """Отправка клиенту логина и пароля."""
    user = request.user

    template = (
        "customer/send_message.html"
        if user.groups.filter(name="admin").exists()
        else "employe/custumer/send_message.html"
    )

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_edit_customers"]
    ):
        context = {}
        context["client"] = get_object_or_404(Custumer, id=pk)

        if request.method == "POST":
            email = request.POST.get("email")
            if not email:
                context["error"] = "Требуется адрес электронной почты."
                return render(request, template, context)

            if CustomUser.objects.filter(Q(email=email)).exists():
                context["error"] = "E-mail уже зарегистрирован."
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
                f"Здравствуйте, {context['client'].full_name}!\n\n"
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
                    "recipient_name": context["client"].full_name,
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
                with transaction.atomic():
                    user = CustomUser.objects.create(
                        first_name=context["client"].full_name,
                        username=email,
                        email=email,
                        company=request.user.company,
                        password=make_password(password),
                    )
                    group, created = Group.objects.get_or_create(name="client")
                    user.groups.add(group)
                    context["client"].user = user
                    context["client"].is_send = True
                    context["client"].save()
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
                return redirect("customer:customer_list")
            except Exception as e:
                context["error"] = str(e)
                return render(request, template, context)
        return render(request, template, context)
    return render(request, "page_404.html")


@login_required
def resend_client_credentials(request, pk):
    """Повторная отправка данных для входа клиенту."""
    user = request.user

    # Проверяем разрешения пользователя
    user_permissions = get_user_permissions(user)

    if not (
        user.groups.filter(name="admin").exists()
        or user_permissions["can_edit_customers"]
    ):
        return render(request, "page_404.html")

    client = get_object_or_404(Custumer, id=pk)

    # Проверяем, что у клиента уже создан пользователь
    if not client.user:
        messages.error(
            request,
            "У клиента еще не создан аккаунт. "
            "Сначала отправьте данные для первого входа.",
        )
        return redirect("customer:customer_list")

    # Генерируем новый пароль
    alphabet = string.ascii_letters + string.digits + string.punctuation
    new_password = "".join(secrets.choice(alphabet) for _ in range(8))

    # Формируем письмо
    subject = "Восстановление доступа к аккаунту"
    message = (
        f"Здравствуйте, {client.full_name}!\n\n"
        "Мы сформировали для вас новый временный пароль для входа.\n"
        f"Логин: {client.user.email}\n"
        f"Временный пароль: {new_password}\n\n"
        "После входа система запросит обязательную смену пароля.\n"
        f"Вход в систему: {request.build_absolute_uri(reverse('sign_in'))}\n"
        f"Смена пароля после входа: {request.build_absolute_uri(reverse('force_password_change'))}\n\n"
        "Если вы не запрашивали доступ, сообщите администратору."
    )
    html_message = render_to_string(
        "emails/temporary_access.html",
        {
            "recipient_name": client.full_name,
            "login_email": client.user.email,
            "temporary_password": new_password,
            "login_link": request.build_absolute_uri(reverse("sign_in")),
            "password_change_link": request.build_absolute_uri(
                reverse("force_password_change")
            ),
            "support_email": prettify_email_address(settings.EMAIL_REPLY_TO),
        },
    )
    extra_headers = {
        "Reply-To": settings.EMAIL_REPLY_TO,
        "List-Unsubscribe": (
            f"<mailto:{settings.EMAIL_UNSUBSCRIBE_EMAIL}?subject=unsubscribe>"
        ),
    }
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [client.user.email]

    try:
        with transaction.atomic():
            client.user.password = make_password(new_password)
            client.user.save()
            set_temporary_password_state(client.user)
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
        messages.success(
            request,
            f"Данные для входа успешно отправлены на {client.user.email}",
        )
    except Exception as e:
        messages.error(request, f"Ошибка при отправке email: {str(e)}")

    return redirect("customer:customer_list")


@admin_required
@require_POST
@transaction.atomic
def update_balance(request):
    if not request.user.groups.filter(name="admin").exists():
        return JsonResponse(
            {"success": False, "error": "Нет прав"}, status=403
        )
    try:
        data = json.loads(request.body)
        custumer_id = int(data.get("custumer_id"))
        balance = int(data.get("balance"))
        if balance < 0:
            raise ValueError
    except Exception:
        return JsonResponse(
            {"success": False, "error": "Некорректные данные"}, status=400
        )
    custumer = Custumer.objects.filter(id=custumer_id).first()
    if not custumer:
        return JsonResponse(
            {"success": False, "error": "Клиент не найден"}, status=404
        )
    if custumer.balance > balance:
        # Штраф - уменьшение баланса
        PointsHistory.objects.create(
            custumer=custumer,
            points=-(custumer.balance - balance),  # Отрицательное значение
            reason=ReasonTextChoices.MANUAL,
            awarded_by=request.user,
            description=data.get("description"),
        )
    else:
        # Награда - увеличение баланса
        PointsHistory.objects.create(
            custumer=custumer,
            points=balance - custumer.balance,  # Положительное значение
            reason=ReasonTextChoices.MANUAL,
            awarded_by=request.user,
            description=data.get("description"),
        )
    custumer.balance = balance
    custumer.save()
    return JsonResponse({"success": True})
