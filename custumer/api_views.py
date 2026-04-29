from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from custumer.services.home import (
    get_active_subscriptions_data,
    get_customer_with_relations,
    get_distance_summary,
    get_group_ratings_data,
    get_news_data,
    get_team_members_data,
    get_trainings_today_data,
)


def _require_customer(user):
    return get_customer_with_relations(user)


def _not_found_response():
    return JsonResponse({"detail": "Клиент не найден"}, status=404)


def _user_is_client(user):
    return user.groups.filter(name="client").exists()


@login_required
@user_passes_test(_user_is_client, login_url="logout_user")
@require_GET
def home_trainings(request):
    custumer = _require_customer(request.user)
    if not custumer:
        return _not_found_response()
    trainings = get_trainings_today_data(custumer)
    return JsonResponse({"trainings": trainings})


@login_required
@user_passes_test(_user_is_client, login_url="logout_user")
@require_GET
def home_subscriptions(request):
    custumer = _require_customer(request.user)
    if not custumer:
        return _not_found_response()
    subscriptions = get_active_subscriptions_data(custumer)
    return JsonResponse({"subscriptions": subscriptions})


@login_required
@user_passes_test(_user_is_client, login_url="logout_user")
@require_GET
def home_news(request):
    custumer = _require_customer(request.user)
    if not custumer:
        return _not_found_response()
    news = get_news_data(custumer)
    return JsonResponse({"news": news})


@login_required
@user_passes_test(_user_is_client, login_url="logout_user")
@require_GET
def home_group_ratings(request):
    custumer = _require_customer(request.user)
    if not custumer:
        return _not_found_response()
    data = get_group_ratings_data(custumer)
    return JsonResponse(data)


@login_required
@user_passes_test(_user_is_client, login_url="logout_user")
@require_GET
def home_team_members(request):
    custumer = _require_customer(request.user)
    if not custumer:
        return _not_found_response()
    data = get_team_members_data(custumer)
    return JsonResponse(data)


@login_required
@user_passes_test(_user_is_client, login_url="logout_user")
@require_GET
def home_distances(request):
    custumer = _require_customer(request.user)
    if not custumer:
        return _not_found_response()
    summary = get_distance_summary(custumer)
    return JsonResponse({"week": summary.week, "year": summary.year})
