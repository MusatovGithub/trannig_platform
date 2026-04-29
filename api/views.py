import json
from datetime import datetime, timedelta
from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseNotAllowed, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from achievements.models import Achievement
from api.models import ApiToken
from competitions.models import Competitions, CustumerCompetitionResult
from competitions.services import (
    CompetitionResultError,
    create_competition_result,
    update_competition_result_instance,
)
from custumer.models import (
    ATTENDANCE_SCORE,
    Cashier,
    Custumer,
    CustumerDocs,
    CustumerRepresentatives,
    CustumerSubscription,
    CustumerSubscriptonPayment,
    SportCategory,
    SubscriptionTemplate,
)
from custumer.payment.services import get_unpaid_attendances_summary_by_company
from custumer.services.home import (
    get_active_subscriptions_data,
    get_company_group_ratings_data,
    get_customer_with_relations,
    get_distance_summary,
    get_group_ratings_data,
    get_news_data,
    get_team_members_data,
    get_trainings_today_data,
)
from custumer.subscription.services import (
    create_subscription_with_payment,
    ensure_can_add_subscription,
)
from employe.utils import (
    can_add_attendance,
    can_edit_competitions,
    can_manage_competition_results,
    get_user_permissions,
)
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)
from groups_custumer.services import (
    AttendanceBlockedError,
    AttendanceValidationError,
    get_attendance_css_class,
    get_attendance_display_text,
    process_attendance_mark,
)
from market.models import Order

COACH_SECTIONS = [
    "Главная",
    "Клиенты",
    "Группы",
    "Занятия",
    "Сотрудники",
    "Достижения",
    "Новости",
    "Соревнования",
    "Испытания",
    "Магазин",
    "Мой профиль",
]
CLIENT_SECTIONS = [
    "Главная",
    "Мои достижения",
    "Дневник",
    "Мои соревнования",
    "Испытания",
    "Магазин",
    "Мои покупки",
    "Мой профиль",
]
ASSISTANT_SECTION_PERMISSIONS = {
    "Клиенты": {
        "Может просматривать клиентов",
        "Может просматривать только своих клиентов",
        "Может просматривать клиентов только в своих группах",
    },
    "Группы": {
        "Может просматривать группы",
        "Может просматривать только свои группы",
    },
    "Занятия": {
        "Может просматривать занятия только своих групп",
        "Может добавлять занятия",
    },
    "Сотрудники": {"Может просматривать сотрудников"},
    "Соревнования": {
        "Может просматривать соревнования",
        "Может создавать соревнования",
        "Может редактировать соревнования",
        "Может управлять результатами соревнований",
    },
}


def api_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = get_request_token(request)
        if token:
            request.api_token = token
            request.user = token.user

        if not request.user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required."},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def api_token_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = get_request_token(request)
        if not token:
            return JsonResponse({"detail": "API token required."}, status=401)

        request.api_token = token
        request.user = token.user
        return view_func(request, *args, **kwargs)

    return wrapper


def api_permission_required(permission_func):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not permission_func(request.user):
                return JsonResponse({"detail": "Permission denied."}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def parse_json_body(request):
    if not request.body:
        return {}

    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON body.") from exc


def json_body_or_error(request):
    try:
        return parse_json_body(request), None
    except ValueError as exc:
        return None, JsonResponse({"detail": str(exc)}, status=400)


def get_request_token(request):
    auth_header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not auth_header.startswith(prefix):
        return None

    raw_token = auth_header[len(prefix) :].strip()
    return ApiToken.authenticate(raw_token)


def serialize_date(value):
    return value.isoformat() if value else None


def serialize_category(category):
    if not category:
        return None
    return {
        "id": category.id,
        "name": category.name,
        "level": category.level,
        "short_name": category.get_short_name(),
    }


def serialize_customer(customer):
    groups = [
        {"id": group.id, "name": group.name}
        for group in customer.groups.all()
    ]
    return {
        "id": customer.id,
        "full_name": customer.full_name,
        "phone": customer.phone,
        "birth_date": serialize_date(customer.birth_date),
        "sport_category": serialize_category(customer.sport_category),
        "groups": groups,
    }


def serialize_competition(competition):
    return {
        "id": competition.id,
        "name": competition.name,
        "location": competition.location,
        "date": serialize_date(competition.date),
        "end_date": serialize_date(competition.end_date),
        "status": competition.status,
    }


def get_user_mobile_sections(user, groups, permissions):
    group_set = set(groups)
    permission_set = set(permissions)

    if "client" in group_set or hasattr(user, "client_profile"):
        return CLIENT_SECTIONS
    if "admin" in group_set:
        return COACH_SECTIONS
    if "assistant" in group_set:
        sections = ["Главная"]
        for section in COACH_SECTIONS[1:]:
            required = ASSISTANT_SECTION_PERMISSIONS.get(section)
            if not required or required & permission_set:
                sections.append(section)
        return sections
    return ["Главная"]


def get_user_account_type(user, groups):
    group_set = set(groups)
    if "client" in group_set or hasattr(user, "client_profile"):
        return "client"
    if "admin" in group_set:
        return "school"
    if "assistant" in group_set:
        return "assistant"
    return "user"


def serialize_user(user):
    groups = list(user.groups.values_list("name", flat=True))
    permissions = [] if "admin" in groups else get_user_permissions(user)
    company = user_company(user)
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "groups": groups,
        "account_type": get_user_account_type(user, groups),
        "permissions": permissions,
        "mobile_sections": get_user_mobile_sections(
            user,
            groups,
            permissions,
        ),
        "company": (
            {"id": company.id, "name": company.name}
            if company
            else None
        ),
        "must_change_password": user.must_change_password,
    }


def serialize_result(result):
    return {
        "id": result.id,
        "competition_id": result.competition_id,
        "customer": serialize_customer(result.customer),
        "distance": result.distance,
        "discipline": result.discipline,
        "style": result.style,
        "style_label": result.get_style_display,
        "result_time": result.format_time(),
        "place": result.place,
        "is_disqualified": result.is_disqualified,
        "disqualification_comment": result.disqualification_comment,
        "sport_category": serialize_category(result.sport_category),
    }


def serialize_dashboard_date(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def normalize_dashboard_item(item):
    if isinstance(item, dict):
        return {
            key: normalize_dashboard_item(value)
            for key, value in item.items()
        }
    if isinstance(item, list):
        return [normalize_dashboard_item(value) for value in item]
    return serialize_dashboard_date(item)


def serialize_attendance(attendance):
    return {
        "id": attendance.id,
        "customer": serialize_customer(attendance.custumer),
        "status": attendance.attendance_status,
        "display_text": get_attendance_display_text(
            attendance.attendance_status
        ),
        "css_class": get_attendance_css_class(attendance.attendance_status),
        "comment": attendance.comment or "",
        "payment_status": attendance.payment_status_display,
        "used_subscription_id": attendance.used_subscription_id,
    }


def serialize_diary_entry(attendance):
    group_class = attendance.gr_class
    return {
        "id": attendance.id,
        "date": serialize_date(attendance.date),
        "time": attendance.class_time.isoformat()
        if attendance.class_time
        else None,
        "class_name": group_class.name if group_class else "Занятие",
        "group": (
            {
                "id": group_class.groups_id.id,
                "name": group_class.groups_id.name,
            }
            if group_class and group_class.groups_id
            else None
        ),
        "trainer_name": (
            group_class.employe.full_name
            if group_class and group_class.employe
            else ""
        ),
        "status": attendance.attendance_status,
        "display_text": get_attendance_display_text(
            attendance.attendance_status
        ),
        "score": ATTENDANCE_SCORE.get(attendance.attendance_status),
        "comment": attendance.comment or "",
    }


def serialize_subscription(subscription):
    return {
        "id": subscription.id,
        "groups": [
            {"id": group.id, "name": group.name}
            for group in subscription.groups.all()
        ],
        "number_classes": subscription.number_classes,
        "used_classes": subscription.remained or 0,
        "classes_left": subscription.count_of_trainnig_left,
        "start_date": serialize_date(subscription.start_date),
        "end_date": serialize_date(subscription.end_date),
        "days_left": subscription.days_left,
        "unlimited": subscription.unlimited,
        "is_free": subscription.is_free,
        "is_closed": subscription.is_blok,
        "payment_status": subscription.get_attendance_status_display(),
        "total_cost": subscription.total_cost,
    }


def serialize_cashier(cashier):
    return {
        "id": cashier.id,
        "name": cashier.name,
    }


def serialize_subscription_template(template):
    return {
        "id": template.id,
        "name": template.name,
        "number_classes": template.number_classes,
        "unlimited": template.unlimited,
        "price": template.price,
        "expired": template.expired,
        "is_free": template.is_free,
    }


def serialize_payment(payment):
    return {
        "id": payment.id,
        "group": (
            {"id": payment.groups.id, "name": payment.groups.name}
            if payment.groups
            else None
        ),
        "subscription_id": payment.subscription_id,
        "attendance_id": payment.attendance_record_id,
        "amount": payment.summ,
        "payment_date": serialize_date(payment.summ_date),
        "lesson_date": serialize_date(payment.sub_date),
        "is_paid": payment.is_pay,
        "is_closed": payment.is_blok,
    }


def serialize_order(order):
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "customer_name": order.customer.get_full_name()
        or order.customer.username,
        "status": order.status,
        "status_label": order.get_status_display(),
        "total_amount": order.total_amount,
        "created_at": order.created_at.isoformat()
        if order.created_at
        else None,
    }


def serialize_document(document):
    return {
        "id": document.id,
        "name": document.name or "",
        "file": document.files.url if document.files else "",
    }


def serialize_representative(representative):
    return {
        "id": representative.id,
        "full_name": representative.full_name or "",
        "phone": representative.phone or "",
        "work": representative.work or "",
        "type": representative.type.name if representative.type else "",
    }


def serialize_achievement(achievement, active=False):
    image = achievement.image.url if achievement.image else ""
    return {
        "id": achievement.id,
        "name": achievement.name,
        "description": achievement.description or "",
        "image": image,
        "tag": achievement.tag,
        "points": achievement.points,
        "active": active,
    }


def serialize_group(group):
    return {
        "id": group.id,
        "name": group.name,
        "type_sport": group.type_sport.name if group.type_sport else "",
        "start_training": serialize_date(group.strat_training),
        "end_training": serialize_date(group.end_training),
        "trainers": [
            {"id": trainer.id, "full_name": trainer.full_name}
            for trainer in group.employe_id.all()
        ],
    }


def serialize_class(group_class, attendances=None):
    payload = {
        "id": group_class.id,
        "name": group_class.name or "",
        "date": serialize_date(group_class.date),
        "start": group_class.strat.isoformat() if group_class.strat else None,
        "end": group_class.end.isoformat() if group_class.end else None,
        "group": (
            {
                "id": group_class.groups_id.id,
                "name": group_class.groups_id.name,
            }
            if group_class.groups_id
            else None
        ),
    }
    if attendances is not None:
        payload["attendances"] = [
            serialize_attendance(attendance) for attendance in attendances
        ]
    return payload


def serialize_training_task(group_class):
    programs = list(group_class.classes.all())
    water_parts = []
    for program in programs:
        parts = [
            program.stages,
            program.distance,
            program.style,
            program.comments,
        ]
        text = " · ".join(part for part in parts if part)
        if program.rest:
            text = f"{text} · отдых {program.rest}" if text else program.rest
        if text:
            water_parts.append(text)

    return {
        "class_id": group_class.id,
        "date": serialize_date(group_class.date),
        "start": group_class.strat.isoformat() if group_class.strat else None,
        "group": (
            {
                "id": group_class.groups_id.id,
                "name": group_class.groups_id.name,
            }
            if group_class.groups_id
            else None
        ),
        "gym_task": group_class.comment or "",
        "water_task": "\n".join(water_parts),
    }


def user_company(user):
    return getattr(user, "company", None)


def get_client_customer_or_response(user):
    customer = get_customer_with_relations(user)
    if not customer:
        return None, JsonResponse(
            {"detail": "Client profile not found."},
            status=404,
        )
    return customer, None


def get_company_competition_or_response(competition_id, user):
    company = user_company(user)
    competition = Competitions.objects.filter(
        id=competition_id,
        owner__company=company,
    ).first()
    if not competition:
        return None, JsonResponse(
            {"detail": "Competition not found."},
            status=404,
        )
    return competition, None


def get_company_customer_or_response(customer_id, user):
    company = user_company(user)
    customer = (
        Custumer.objects.select_related("sport_category")
        .prefetch_related("groups")
        .filter(id=customer_id, company=company)
        .first()
    )
    if not customer:
        return None, JsonResponse({"detail": "Customer not found."}, status=404)
    return customer, None


def parse_api_date(value, field_name):
    if not value:
        raise ValueError(f"{field_name} is required.")

    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(value), date_format).date()
        except ValueError:
            continue
    raise ValueError(f"{field_name} has invalid date format.")


def parse_int_or_none(value, field_name):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number.") from None


def get_company_result_or_response(result_id, user):
    result = (
        CustumerCompetitionResult.objects.select_related(
            "competition__owner",
            "customer",
            "sport_category",
        )
        .prefetch_related("customer__groups")
        .filter(id=result_id, competition__owner__company=user_company(user))
        .first()
    )
    if not result:
        return None, JsonResponse({"detail": "Result not found."}, status=404)
    return result, None


@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    return JsonResponse({"detail": "CSRF cookie set."})


@csrf_exempt
@require_http_methods(["POST"])
def login_user(request):
    payload, response = json_body_or_error(request)
    if response:
        return response

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        return JsonResponse(
            {"detail": "Username and password are required."},
            status=400,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=400)

    login(request, user)
    _, token = ApiToken.create_token(
        user,
        name=str(payload.get("device_name", "")).strip(),
    )
    return JsonResponse({"user": serialize_user(user), "token": token})


@csrf_exempt
@api_login_required
@require_http_methods(["POST"])
def logout_user(request):
    api_token = getattr(request, "api_token", None)
    if api_token:
        api_token.delete()
        return JsonResponse({"success": True})

    logout(request)
    return JsonResponse({"success": True})


@api_login_required
@require_GET
def me(request):
    return JsonResponse({"user": serialize_user(request.user)})


@api_login_required
@require_GET
def client_dashboard(request):
    customer, response = get_client_customer_or_response(request.user)
    if response:
        return response

    today = timezone.localdate()
    today_classes = (
        GroupClasses.objects.filter(
            company=customer.company,
            date=today,
            groups_id__in=customer.groups.all(),
        )
        .select_related("groups_id")
        .prefetch_related("classes")
        .order_by("strat", "id")[:6]
    )
    distances = get_distance_summary(customer)
    payload = {
        "customer": serialize_customer(customer),
        "achievements_count": customer.achievements.count(),
        "trainings_today": get_trainings_today_data(customer),
        "training_tasks_today": [
            serialize_training_task(group_class)
            for group_class in today_classes
        ],
        "active_challenge": None,
        "subscriptions": get_active_subscriptions_data(customer),
        "group_ratings": get_group_ratings_data(customer),
        "company_group_ratings": get_company_group_ratings_data(customer),
        "team": get_team_members_data(customer),
        "news": get_news_data(customer),
        "distances": {"week": distances.week, "year": distances.year},
    }
    return JsonResponse(normalize_dashboard_item(payload))


@api_login_required
@require_GET
def client_diary(request):
    customer, response = get_client_customer_or_response(request.user)
    if response:
        return response

    today = timezone.localdate()
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    group_id = request.GET.get("group_id")

    try:
        start_date = (
            datetime.strptime(date_from, "%Y-%m-%d").date()
            if date_from
            else today - timedelta(days=30)
        )
        end_date = (
            datetime.strptime(date_to, "%Y-%m-%d").date()
            if date_to
            else today + timedelta(days=30)
        )
    except ValueError:
        return JsonResponse({"detail": "Invalid date."}, status=400)

    entries = GroupClassessCustumer.objects.filter(
        custumer=customer,
        date__gte=start_date,
        date__lte=end_date,
    )
    if group_id:
        entries = entries.filter(gr_class__groups_id__id=group_id)

    entries = (
        entries.select_related(
            "gr_class",
            "gr_class__groups_id",
            "gr_class__employe",
            "owner",
        )
        .order_by("-date", "-class_time", "-id")[:100]
    )

    return JsonResponse(
        {
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "entries": [
                serialize_diary_entry(entry)
                for entry in entries
            ],
        }
    )


@api_login_required
@require_GET
def client_subscriptions(request):
    customer, response = get_client_customer_or_response(request.user)
    if response:
        return response

    queryset = (
        CustumerSubscription.objects.filter(custumer=customer)
        .prefetch_related("groups")
        .order_by("is_blok", "-start_date", "-id")
    )
    active_only = request.GET.get("active")
    if active_only in {"1", "true", "yes"}:
        today = timezone.localdate()
        queryset = queryset.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_blok=False,
        )

    return JsonResponse(
        {
            "subscriptions": [
                serialize_subscription(subscription)
                for subscription in queryset[:100]
            ]
        }
    )


@api_login_required
@require_GET
def client_achievements(request):
    customer, response = get_client_customer_or_response(request.user)
    if response:
        return response

    active_ids = set(customer.achievements.values_list("id", flat=True))
    achievements = Achievement.objects.filter(
        owner_id=customer.owner_id,
    ).order_by("-id")

    return JsonResponse(
        {
            "achievements": [
                serialize_achievement(
                    achievement,
                    active=achievement.id in active_ids,
                )
                for achievement in achievements[:100]
            ],
            "active_count": len(active_ids),
        }
    )


@api_login_required
@require_GET
def client_competition_results(request):
    customer, response = get_client_customer_or_response(request.user)
    if response:
        return response

    results = (
        CustumerCompetitionResult.objects.filter(customer=customer)
        .select_related("competition", "customer", "sport_category")
        .order_by("-competition__date", "-id")
    )

    return JsonResponse(
        {
            "results": [
                serialize_result(result)
                for result in results[:100]
            ]
        }
    )


@api_login_required
@require_GET
def coach_dashboard(request):
    company = user_company(request.user)
    if not company:
        return JsonResponse({"detail": "Company not found."}, status=404)

    today = timezone.localdate()
    customers_count = Custumer.objects.filter(
        company=company,
        is_none=False,
    ).count()
    groups_count = GroupsClass.objects.filter(company=company).count()
    competitions_count = Competitions.objects.filter(
        owner__company=company,
        status="open",
    ).count()
    recent_results = (
        CustumerCompetitionResult.objects.filter(
            competition__owner__company=company,
        )
        .select_related("competition", "customer")
        .order_by("-competition__date", "-id")[:8]
    )
    today_classes = (
        GroupClasses.objects.filter(company=company, date=today)
        .select_related("groups_id", "employe")
        .prefetch_related("classes")
        .order_by("strat", "id")[:8]
    )
    expired_subscriptions = (
        CustumerSubscription.objects.filter(
            custumer__company=company,
            end_date__lt=today,
            is_blok=False,
        )
        .select_related("custumer")
        .prefetch_related("groups")
        .order_by("end_date")[:8]
    )
    unpaid_lessons = get_unpaid_attendances_summary_by_company(company.id)[:8]
    pending_orders = (
        Order.objects.filter(
            customer__company=company,
            status__in=["PENDING", "CONFIRMED", "PROCESSING"],
        )
        .select_related("customer")
        .order_by("-created_at")[:8]
    )
    birthdays_today = (
        Custumer.objects.filter(
            company=company,
            is_none=False,
            birth_date__month=today.month,
            birth_date__day=today.day,
        )
        .select_related("sport_category")
        .prefetch_related("groups")
        .order_by("full_name")[:8]
    )

    return JsonResponse(
        {
            "summary": {
                "customers_count": customers_count,
                "groups_count": groups_count,
                "open_competitions_count": competitions_count,
                "today_classes_count": GroupClasses.objects.filter(
                    company=company,
                    date=today,
                ).count(),
                "expired_subscriptions_count": (
                    CustumerSubscription.objects.filter(
                        custumer__company=company,
                        end_date__lt=today,
                        is_blok=False,
                    ).count()
                ),
                "unpaid_lessons_count": sum(
                    item["count"] for item in unpaid_lessons
                ),
                "pending_orders_count": Order.objects.filter(
                    customer__company=company,
                    status__in=["PENDING", "CONFIRMED", "PROCESSING"],
                ).count(),
                "active_challenges_count": 0,
            },
            "today_classes": [
                serialize_class(group_class) for group_class in today_classes
            ],
            "today_training_tasks": [
                serialize_training_task(group_class)
                for group_class in today_classes
            ],
            "birthdays_today": [
                serialize_customer(customer)
                for customer in birthdays_today
            ],
            "expired_subscriptions": [
                {
                    **serialize_subscription(subscription),
                    "customer": serialize_customer(subscription.custumer),
                }
                for subscription in expired_subscriptions
            ],
            "unpaid_lessons": [
                {
                    "customer_id": item["custumer_id"],
                    "customer_name": item["custumer__full_name"],
                    "group_id": item["gr_class__groups_id"],
                    "group_name": item["gr_class__groups_id__name"],
                    "count": item["count"],
                }
                for item in unpaid_lessons
            ],
            "pending_orders": [
                serialize_order(order) for order in pending_orders
            ],
            "recent_results": [
                {
                    "id": result.id,
                    "customer_name": result.customer.full_name,
                    "competition_name": result.competition.name,
                    "distance": result.distance,
                    "discipline": result.discipline,
                    "result_time": result.format_time(),
                    "place": result.place,
                }
                for result in recent_results
            ],
        }
    )


@api_login_required
@require_GET
def coach_classes(request):
    company = user_company(request.user)
    if not company:
        return JsonResponse({"detail": "Company not found."}, status=404)

    date_value = request.GET.get("date")
    if date_value:
        try:
            from datetime import datetime

            selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"detail": "Invalid date."}, status=400)
    else:
        from django.utils import timezone

        selected_date = timezone.now().date()

    classes = (
        GroupClasses.objects.filter(company=company, date=selected_date)
        .select_related("groups_id")
        .order_by("strat", "id")
    )
    attendance_map = {}
    attendances = (
        GroupClassessCustumer.objects.filter(
            gr_class__in=classes,
            is_none=False,
        )
        .select_related(
            "custumer",
            "custumer__sport_category",
            "gr_class",
            "used_subscription",
        )
        .prefetch_related("custumer__groups")
        .order_by("custumer__full_name")
    )
    for attendance in attendances:
        attendance_map.setdefault(attendance.gr_class_id, []).append(attendance)

    return JsonResponse(
        {
            "date": selected_date.isoformat(),
            "classes": [
                serialize_class(
                    group_class,
                    attendance_map.get(group_class.id, []),
                )
                for group_class in classes
            ],
        }
    )


@api_login_required
@require_GET
def coach_customer_detail(request, customer_id):
    customer, response = get_company_customer_or_response(
        customer_id,
        request.user,
    )
    if response:
        return response

    customer = (
        Custumer.objects.filter(id=customer.id)
        .select_related("sport_category", "gender", "company", "owner")
        .prefetch_related("groups", "achievements")
        .first()
    )
    subscriptions = (
        CustumerSubscription.objects.filter(custumer=customer)
        .prefetch_related("groups")
        .order_by("is_blok", "-start_date", "-id")[:20]
    )
    payments = (
        CustumerSubscriptonPayment.objects.filter(custumer=customer)
        .select_related("groups", "subscription", "attendance_record")
        .order_by("-summ_date", "-sub_date", "-id")[:20]
    )
    documents = CustumerDocs.objects.filter(custumer=customer).order_by("id")
    representatives = (
        CustumerRepresentatives.objects.filter(custumer=customer)
        .select_related("type")
        .order_by("id")
    )
    diary = (
        GroupClassessCustumer.objects.filter(custumer=customer)
        .select_related("gr_class", "gr_class__groups_id", "gr_class__employe")
        .order_by("-date", "-class_time", "-id")[:20]
    )
    results = (
        CustumerCompetitionResult.objects.filter(customer=customer)
        .select_related("competition", "customer", "sport_category")
        .order_by("-competition__date", "-id")[:20]
    )

    return JsonResponse(
        {
            "customer": serialize_customer(customer),
            "profile": {
                "email": customer.email or "",
                "address": customer.address or "",
                "gender": customer.gender.name if customer.gender else "",
                "contract_number": customer.contract_number or "",
                "contract_type": customer.contract_type or "",
                "start_date": serialize_date(customer.strat_date),
            },
            "links": {
                "profile": f"/customer/detail/{customer.id}/",
                "subscriptions": f"/customer/{customer.id}/subscriptions/",
                "payments": f"/customer/payment/history/{customer.id}/",
                "documents": f"/customer/{customer.id}/docs/",
                "representatives": (
                    f"/customer/{customer.id}/representatives/"
                ),
                "lesson_history": f"/customer/{customer.id}/payment/",
                "achievements": f"/customer/{customer.id}/achievements/",
            },
            "groups": [
                serialize_group(group) for group in customer.groups.all()
            ],
            "subscriptions": [
                serialize_subscription(subscription)
                for subscription in subscriptions
            ],
            "payments": [serialize_payment(payment) for payment in payments],
            "documents": [
                serialize_document(document) for document in documents
            ],
            "representatives": [
                serialize_representative(representative)
                for representative in representatives
            ],
            "diary": [serialize_diary_entry(entry) for entry in diary],
            "achievements": [
                serialize_achievement(achievement, active=True)
                for achievement in customer.achievements.all()
            ],
            "competition_results": [
                serialize_result(result) for result in results
            ],
        }
    )


@csrf_exempt
@api_login_required
@require_http_methods(["POST"])
def coach_customer_issue_subscription(request, customer_id):
    if not ensure_can_add_subscription(request.user):
        return JsonResponse({"detail": "Permission denied."}, status=403)

    customer, response = get_company_customer_or_response(
        customer_id,
        request.user,
    )
    if response:
        return response

    payload, response = json_body_or_error(request)
    if response:
        return response

    try:
        group_ids = payload.get("group_ids") or []
        if not group_ids:
            raise ValueError("group_ids is required.")

        groups = GroupsClass.objects.filter(
            id__in=group_ids,
            company=request.user.company,
        )
        if groups.count() != len(set(int(group_id) for group_id in group_ids)):
            raise ValueError("Some groups are unavailable.")

        start_date = parse_api_date(payload.get("start_date"), "start_date")
        end_date = parse_api_date(payload.get("end_date"), "end_date")
        if end_date < start_date:
            raise ValueError("end_date must be after start_date.")

        unlimited = bool(payload.get("unlimited", False))
        is_free = bool(payload.get("is_free", False))
        number = parse_int_or_none(payload.get("number_classes"), "number_classes")
        if not unlimited and not number:
            raise ValueError("number_classes is required for limited subscription.")

        price = parse_int_or_none(payload.get("total_cost"), "total_cost") or 0
        summ = parse_int_or_none(payload.get("payment_amount"), "payment_amount") or 0
        cashier_id = parse_int_or_none(payload.get("cashier_id"), "cashier_id")
        if summ and not cashier_id:
            raise ValueError("cashier_id is required when payment_amount is set.")

        if cashier_id and not Cashier.objects.filter(
            id=cashier_id,
            company=request.user.company,
        ).exists():
            raise ValueError("cashier_id is unavailable.")

        existing_subscription = CustumerSubscription.objects.filter(
            custumer=customer,
            groups__in=groups,
            start_date__lte=end_date,
            end_date__gte=start_date,
            is_blok=False,
        ).exists()
        if existing_subscription:
            raise ValueError("В этом диапазоне уже есть абонемент.")

        date_summ = payload.get("payment_date") or ""
        if date_summ and "-" in str(date_summ):
            date_summ = parse_api_date(date_summ, "payment_date").strftime(
                "%d.%m.%Y"
            )
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    subscription, payments = create_subscription_with_payment(
        custumer=customer,
        groups=groups,
        number=number,
        start_date=start_date,
        end_date=end_date,
        unlimited=unlimited,
        is_free=is_free,
        price=price,
        summ=summ,
        cashier_id=cashier_id,
        date_summ=date_summ,
        company=request.user.company,
        owner=request.user,
    )

    return JsonResponse(
        {
            "subscription": serialize_subscription(subscription),
            "payments": [serialize_payment(payment) for payment in payments],
        },
        status=201,
    )


@api_login_required
@require_GET
def coach_subscription_form_options(request):
    company = user_company(request.user)
    if not company:
        return JsonResponse({"detail": "Company not found."}, status=404)

    groups = GroupsClass.objects.filter(company=company).order_by("name")
    cashiers = Cashier.objects.filter(company=company).order_by("name")
    templates = SubscriptionTemplate.objects.filter(company=company).order_by(
        "name"
    )
    return JsonResponse(
        {
            "groups": [serialize_group(group) for group in groups],
            "cashiers": [serialize_cashier(cashier) for cashier in cashiers],
            "templates": [
                serialize_subscription_template(template)
                for template in templates
            ],
        }
    )


@api_login_required
@require_GET
def coach_groups(request):
    company = user_company(request.user)
    if not company:
        return JsonResponse({"detail": "Company not found."}, status=404)

    groups = (
        GroupsClass.objects.filter(company=company)
        .prefetch_related("employe_id", "custumer_set")
        .order_by("position", "name")
    )
    return JsonResponse(
        {
            "groups": [
                {
                    **serialize_group(group),
                    "customers_count": group.custumer_set.count(),
                }
                for group in groups
            ]
        }
    )


@api_login_required
@require_GET
def coach_group_detail(request, group_id):
    company = user_company(request.user)
    group = (
        GroupsClass.objects.filter(id=group_id, company=company)
        .prefetch_related(
            "employe_id",
            "custumer_set",
            "custumer_set__sport_category",
            "group_class",
            "group_class__employe",
        )
        .first()
    )
    if not group:
        return JsonResponse({"detail": "Group not found."}, status=404)

    classes = (
        GroupClasses.objects.filter(groups_id=group)
        .select_related("groups_id", "employe")
        .order_by("-date", "-strat")[:20]
    )
    attendances = (
        GroupClassessCustumer.objects.filter(gr_class__in=classes)
        .select_related("custumer", "custumer__sport_category", "gr_class")
        .prefetch_related("custumer__groups")
        .order_by("custumer__full_name")
    )
    attendance_map = {}
    for attendance in attendances:
        attendance_map.setdefault(attendance.gr_class_id, []).append(attendance)

    return JsonResponse(
        {
            "group": serialize_group(group),
            "links": {
                "detail": f"/groups/detail/{group.id}/",
                "add_customer": f"/group/{group.id}/custumers/create/",
                "add_class": f"/group/{group.id}/classes/add/",
            },
            "customers": [
                serialize_customer(customer)
                for customer in group.custumer_set.all()
            ],
            "classes": [
                serialize_class(
                    group_class,
                    attendance_map.get(group_class.id, []),
                )
                for group_class in classes
            ],
        }
    )


@csrf_exempt
@api_token_required
@api_permission_required(can_add_attendance)
@require_http_methods(["POST"])
def mark_attendance(request, attendance_id):
    payload, response = json_body_or_error(request)
    if response:
        return response

    attendance = (
        GroupClassessCustumer.objects.select_related(
            "custumer",
            "custumer__gender",
            "custumer__company",
            "custumer__owner",
            "custumer__sport_category",
            "gr_class",
            "gr_class__groups_id",
            "used_subscription",
            "company",
            "owner",
        )
        .prefetch_related("custumer__groups", "custumer__custumersubscription_set")
        .filter(id=attendance_id, company=user_company(request.user))
        .first()
    )
    if not attendance:
        return JsonResponse({"detail": "Attendance not found."}, status=404)

    status = str(payload.get("status", "")).strip()
    comment = str(payload.get("comment", "")).strip()
    if not status:
        return JsonResponse({"detail": "Status is required."}, status=400)

    try:
        result = process_attendance_mark(
            attendance=attendance,
            new_status=status,
            comment=comment,
            company=request.user.company,
            owner=request.user,
        )
    except AttendanceValidationError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    except AttendanceBlockedError as exc:
        return JsonResponse({"detail": str(exc)}, status=403)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    attendance.refresh_from_db()
    return JsonResponse(
        {
            "success": True,
            "action": result.get("action"),
            "attendance": serialize_attendance(attendance),
        }
    )


@api_login_required
@require_GET
def customers(request):
    company = user_company(request.user)
    queryset = Custumer.objects.none()
    if company:
        queryset = (
            Custumer.objects.filter(company=company, is_none=False)
            .select_related("sport_category")
            .prefetch_related("groups")
            .order_by("full_name")
        )

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(full_name__icontains=search)

    limit = min(int(request.GET.get("limit", 50)), 200)
    data = [serialize_customer(customer) for customer in queryset[:limit]]
    return JsonResponse({"customers": data})


@api_login_required
@require_GET
def sport_categories(request):
    categories = SportCategory.objects.order_by("level", "name")
    return JsonResponse(
        {"sport_categories": [serialize_category(item) for item in categories]}
    )


@api_login_required
@require_GET
def competitions(request):
    company = user_company(request.user)
    queryset = Competitions.objects.none()
    if company:
        queryset = Competitions.objects.filter(
            owner__company=company,
        ).order_by("-date", "-end_date")

    limit = min(int(request.GET.get("limit", 50)), 200)
    data = [serialize_competition(item) for item in queryset[:limit]]
    return JsonResponse({"competitions": data})


@api_login_required
@require_GET
def competition_detail(request, competition_id):
    company = user_company(request.user)
    competition = (
        Competitions.objects.filter(id=competition_id, owner__company=company)
        .prefetch_related("customers")
        .first()
    )
    if not competition:
        return JsonResponse({"detail": "Competition not found."}, status=404)

    customers_data = [
        serialize_customer(customer)
        for customer in competition.customers.select_related(
            "sport_category"
        ).prefetch_related("groups")
    ]
    return JsonResponse(
        {
            "competition": serialize_competition(competition),
            "customers": customers_data,
        }
    )


@api_login_required
@require_GET
def competition_results(request, competition_id):
    company = user_company(request.user)
    competition_exists = Competitions.objects.filter(
        id=competition_id,
        owner__company=company,
    ).exists()
    if not competition_exists:
        return JsonResponse({"detail": "Competition not found."}, status=404)

    results = (
        CustumerCompetitionResult.objects.filter(
            competition_id=competition_id,
        )
        .select_related("competition", "customer", "sport_category")
        .prefetch_related("customer__groups")
        .order_by("customer__full_name", "distance", "discipline")
    )
    return JsonResponse({"results": [serialize_result(item) for item in results]})


@api_login_required
@api_permission_required(can_edit_competitions)
@require_http_methods(["POST"])
@csrf_exempt
@api_token_required
def competition_participants(request, competition_id):
    competition, response = get_company_competition_or_response(
        competition_id,
        request.user,
    )
    if response:
        return response

    payload, response = json_body_or_error(request)
    if response:
        return response

    customer_ids = payload.get("customer_ids", [])
    if not isinstance(customer_ids, list):
        return JsonResponse(
            {"detail": "customer_ids must be a list."},
            status=400,
        )

    customers_qs = Custumer.objects.filter(
        id__in=customer_ids,
        company=user_company(request.user),
    )
    customers = list(customers_qs)
    found_ids = {customer.id for customer in customers}
    missing_ids = [item for item in customer_ids if item not in found_ids]
    if missing_ids:
        return JsonResponse(
            {"detail": "Some customers were not found.", "ids": missing_ids},
            status=404,
        )

    competition.customers.add(*customers)
    return JsonResponse(
        {
            "success": True,
            "competition": serialize_competition(competition),
            "customers": [serialize_customer(customer) for customer in customers],
        },
        status=201,
    )


@api_login_required
@api_permission_required(can_manage_competition_results)
@require_http_methods(["POST"])
@csrf_exempt
@api_token_required
def create_result(request, competition_id):
    competition, response = get_company_competition_or_response(
        competition_id,
        request.user,
    )
    if response:
        return response

    payload, response = json_body_or_error(request)
    if response:
        return response

    customer, response = get_company_customer_or_response(
        payload.get("customer_id"),
        request.user,
    )
    if response:
        return response

    if not competition.customers.filter(id=customer.id).exists():
        return JsonResponse(
            {"detail": "Customer is not a competition participant."},
            status=400,
        )

    try:
        result, rank_message = create_competition_result(
            competition,
            customer,
            payload,
        )
    except CompetitionResultError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    return JsonResponse(
        {
            "success": True,
            "result": serialize_result(result),
            "rank_message": rank_message,
        },
        status=201,
    )


@api_login_required
@api_permission_required(can_manage_competition_results)
@csrf_exempt
@api_token_required
def result_detail(request, result_id):
    result, response = get_company_result_or_response(result_id, request.user)
    if response:
        return response

    if request.method == "GET":
        return JsonResponse({"result": serialize_result(result)})

    if request.method in ("PUT", "PATCH"):
        payload, response = json_body_or_error(request)
        if response:
            return response

        try:
            result, rank_message = update_competition_result_instance(
                result,
                payload,
            )
        except CompetitionResultError as exc:
            return JsonResponse({"detail": str(exc)}, status=400)

        return JsonResponse(
            {
                "success": True,
                "result": serialize_result(result),
                "rank_message": rank_message,
            }
        )

    if request.method == "DELETE":
        result.delete()
        return JsonResponse({"success": True})

    return HttpResponseNotAllowed(["GET", "PUT", "PATCH", "DELETE"])
