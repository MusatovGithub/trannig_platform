from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.db.models import F
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from base.cache_utils import CACHE_TIMEOUTS
from custumer.models import CustumerSubscription
from custumer.payment.services import (
    get_unpaid_attendances_summary_by_company,
)
from custumer.services.home import get_customer_with_relations
from groups_custumer.models import GroupClasses, GroupsClass


def get_user_groups(user):
    """Кеширует группы пользователя для избежания повторных запросов."""
    if not hasattr(user, "_cached_groups"):
        user._cached_groups = set(user.groups.values_list("name", flat=True))
    return user._cached_groups


def is_admin(user):
    return "admin" in get_user_groups(user)


def is_assistent(user):
    return "assistant" in get_user_groups(user)


def is_client(user):
    return "client" in get_user_groups(user)


@login_required
@user_passes_test(is_admin, login_url="logout_user")
def supervisor_home(request):
    today = timezone.now().date()
    company_id = request.user.company.id

    # Тренировки на сегодня с кешированием
    cache_key = f"company:{company_id}:classes:{today}"
    classess = cache.get(cache_key)
    if classess is None:
        classess = list(
            GroupClasses.objects.filter(
                company=request.user.company, date=today
            )
            .select_related("groups_id", "employe", "company", "owner")
            .prefetch_related("groups_id__employe_id")
            .order_by("strat")
        )
        cache.set(cache_key, classess, CACHE_TIMEOUTS["today_classes"])

    # Неоплаченные посещения (сгруппировано по клиенту и группе)
    unpaid_payments = get_unpaid_attendances_summary_by_company(
        company_id=request.user.company.id
    )

    # Закончились занятия: либо исчерпаны посещения, либо истёк срок
    subs_qs = (
        CustumerSubscription.objects.filter(
            custumer__company=request.user.company, is_blok=False
        )
        .select_related("custumer", "owner", "company")
        .prefetch_related("groups", "payments")
    )

    exhausted_visits_qs = subs_qs.filter(
        unlimited=False,
        number_classes__isnull=False,
        remained__gte=F("number_classes"),
    ).values(
        "id",
        "custumer_id",
        "custumer__full_name",
        "end_date",
        "number_classes",
        "remained",
        "groups__id",
        "attendance_status",
    )

    expired_date_qs = subs_qs.filter(end_date__lt=today).values(
        "id",
        "custumer_id",
        "custumer__full_name",
        "end_date",
        "number_classes",
        "remained",
        "groups__id",
        "attendance_status",
    )

    # Формируем список уведомлений по клиентам (по одному на клиента)
    exhausted_map = {}

    def upsert_notice(row, reason):
        cid = row["custumer_id"]
        if cid in exhausted_map:
            return
        exhausted_map[cid] = {
            "id": row["id"],
            "custumer_id": cid,
            "name": row["custumer__full_name"],
            "reason": reason,
            "end_date": row["end_date"],
            "number_classes": row["number_classes"],
            "remained": row["remained"],
            "group_id": row.get("groups__id"),
            "attendance_status": row.get("attendance_status"),
        }

    for row in exhausted_visits_qs:
        upsert_notice(row, "no_visits")
    for row in expired_date_qs:
        upsert_notice(row, "expired")

    context = {
        "classess": classess,
        "unpaid_payments": unpaid_payments,
        "exhausted_subs": list(exhausted_map.values()),
    }
    context["is_admin"] = is_admin(request.user)
    return render(request, "supervisor/index.html", context)


@login_required
@user_passes_test(is_assistent, login_url="logout_user")
def home_employe(request):
    today = timezone.now().date()
    user = request.user

    # Проверяем права на просмотр групп - оптимизированная версия
    from employe.utils import get_user_permissions

    # Получаем все права пользователя одним запросом
    user_permissions = get_user_permissions(user)

    # Проверяем права на основе полученного списка
    can_view_all_groups = "Может просматривать группы" in user_permissions
    can_view_own_groups = (
        "Может просматривать только свои группы" in user_permissions
    )
    can_view_classes = (
        "Может просматривать занятия только своих групп" in user_permissions
    )

    # Фильтруем занятия в зависимости от прав с оптимизированными запросами
    if can_view_all_groups:
        classess = (
            GroupClasses.objects.filter(company=user.company, date=today)
            .select_related("groups_id", "employe", "company", "owner")
            .prefetch_related("groups_id__employe_id")
            .order_by("strat")
        )
    elif can_view_own_groups or can_view_classes:
        user_groups = GroupsClass.objects.filter(employe_id__user=user)
        classess = (
            GroupClasses.objects.filter(groups_id__in=user_groups, date=today)
            .select_related("groups_id", "employe", "company", "owner")
            .prefetch_related("groups_id__employe_id")
            .order_by("strat")
        )
    else:
        classess = GroupClasses.objects.none()

    context = {"classess": classess}
    return render(request, "employe/home.html", context)


@login_required
@user_passes_test(is_client, login_url="logout_user")
def home_client(request):
    """Главная страница для клиента."""
    user = request.user

    custumer = get_customer_with_relations(user)

    if not custumer:
        return render(
            request,
            "customer/cabinet/home.html",
            {
                "custumer": None,
                "api_urls": {},
            },
        )

    api_urls = {
        "trainings": reverse("customer:home_trainings"),
        "subscriptions": reverse("customer:home_subscriptions"),
        "news": reverse("customer:home_news"),
        "group_ratings": reverse("customer:home_group_ratings"),
        "team_members": reverse("customer:home_team_members"),
        "distances": reverse("customer:home_distances"),
    }

    context = {
        "custumer": custumer,
        "api_urls": api_urls,
        "customer_id": custumer.id,
    }
    return render(request, "customer/cabinet/home.html", context)
