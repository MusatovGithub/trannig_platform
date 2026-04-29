from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Tuple

from django.db.models import Avg, Case, IntegerField, Sum, When
from django.utils import timezone

from competitions.models import CustumerCompetitionResult
from custumer.models import ATTENDANCE_SCORE, Custumer, CustumerSubscription
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)
from news.models import News
from news.schemas import StatusTextChoices
from supervisor.utils import get_client_distances


@dataclass(frozen=True)
class DistanceSummary:
    week: float
    year: float


def get_customer_with_relations(user) -> Custumer | None:
    """
    Возвращает клиента с базовыми данными.
    """
    return (
        Custumer.objects.select_related("company", "user", "sport_category")
        .prefetch_related("groups")
        .filter(user=user)
        .first()
    )


def _collect_group_customers(groups: Iterable) -> Dict[int, List[Custumer]]:
    mapping: Dict[int, List[Custumer]] = {}
    for group in groups:
        # prefetch_related("custumer_set") подготовлен заранее
        mapping[group.id] = list(group.custumer_set.all())
    return mapping


def _aggregate_group_attendances(
    group_ids: Iterable[int], custumers: Iterable
):
    return (
        GroupClassessCustumer.objects.filter(
            gr_class__groups_id__in=group_ids,
            custumer__in=custumers,
            attendance_status__in=ATTENDANCE_SCORE.keys(),
        )
        .values("custumer", "gr_class__groups_id")
        .annotate(
            avg_score=Avg(
                Case(
                    *(
                        When(attendance_status=k, then=v)
                        for k, v in ATTENDANCE_SCORE.items()
                    ),
                    output_field=IntegerField(),
                )
            )
        )
    )


def get_group_ratings_data(custumer: Custumer) -> Dict[str, Any]:
    groups = custumer.groups.prefetch_related("custumer_set").all()
    group_ids = [g.id for g in groups]
    all_group_customers = _collect_group_customers(groups)
    all_customers_flat = [
        customer
        for customers in all_group_customers.values()
        for customer in customers
    ]

    attendances = _aggregate_group_attendances(group_ids, all_customers_flat)

    group_attendance_dict: Dict[int, Dict[int, float]] = {}
    for attendance in attendances:
        group_id = attendance["gr_class__groups_id"]
        customer_id = attendance["custumer"]
        if group_id not in group_attendance_dict:
            group_attendance_dict[group_id] = {}
        group_attendance_dict[group_id][customer_id] = (
            attendance["avg_score"] or 0
        )

    group_ratings: Dict[int, Tuple[float, int | None, int]] = {}
    best_group_data = {
        "id": None,
        "avg": 0,
        "place": None,
        "total": None,
        "name": "",
    }

    for group in groups:
        group_customers = all_group_customers[group.id]
        total_participants = len(group_customers)
        avg_dict = group_attendance_dict.get(group.id, {}).copy()

        for customer_in_group in group_customers:
            if customer_in_group.id not in avg_dict:
                avg_dict[customer_in_group.id] = 0

        sorted_scores = sorted(
            avg_dict.items(),
            key=lambda pair: pair[1] if pair[1] is not None else 0,
            reverse=True,
        )

        my_avg = avg_dict.get(custumer.id, 0) or 0
        my_place = next(
            (
                index + 1
                for index, (customer_id, _) in enumerate(sorted_scores)
                if customer_id == custumer.id
            ),
            None,
        )
        group_ratings[group.id] = (my_avg, my_place, total_participants)

        if my_avg > best_group_data["avg"]:
            best_group_data.update(
                {
                    "id": group.id,
                    "avg": my_avg,
                    "place": my_place,
                    "total": total_participants,
                    "name": group.name,
                }
            )

    return {
        "groups": [
            {
                "id": group.id,
                "name": group.name,
                "average": group_ratings.get(group.id, (0, None, 0))[0],
                "place": group_ratings.get(group.id, (0, None, 0))[1],
                "total": group_ratings.get(group.id, (0, None, 0))[2],
            }
            for group in groups
        ],
        "best_group": best_group_data,
    }


def get_team_members_data(custumer: Custumer) -> Dict[str, Any]:
    company_customers = (
        Custumer.objects.filter(company_id=custumer.company_id)
        .select_related("user", "sport_category")
        .prefetch_related("achievements")
    )

    company_attendances = (
        GroupClassessCustumer.objects.filter(
            custumer__in=company_customers,
            attendance_status__in=ATTENDANCE_SCORE.keys(),
        )
        .values("custumer")
        .annotate(
            avg_score=Avg(
                Case(
                    *(
                        When(attendance_status=k, then=v)
                        for k, v in ATTENDANCE_SCORE.items()
                    ),
                    output_field=None,
                )
            )
        )
    )

    avg_dict = {
        attendance["custumer"]: attendance["avg_score"] or 0
        for attendance in company_attendances
    }

    for customer_id in company_customers.values_list("id", flat=True):
        avg_dict.setdefault(customer_id, 0)

    sorted_team = sorted(
        avg_dict.items(), key=lambda pair: pair[1], reverse=True
    )

    team_avg = avg_dict.get(custumer.id, 0)
    team_place = next(
        (
            index + 1
            for index, (customer_id, _) in enumerate(sorted_team)
            if customer_id == custumer.id
        ),
        None,
    )

    customer_ids: List[int] = list(
        company_customers.values_list("id", flat=True)
    )

    competition_results = {}
    if customer_ids:
        for result in (
            CustumerCompetitionResult.objects.filter(
                customer_id__in=customer_ids, is_disqualified=False
            )
            .select_related("competition")
            .order_by("customer_id", "-competition__date")
        ):
            results_for_customer = competition_results.setdefault(
                result.customer.id, []
            )
            if len(results_for_customer) < 5:
                results_for_customer.append(
                    {
                        "name": result.competition.name,
                        "date": result.competition.date,
                        "distance": result.distance,
                        "place": result.place,
                    }
                )

    members_payload = []
    for index, (customer_id, score) in enumerate(sorted_team):
        member = company_customers.get(id=customer_id)
        if not member:
            continue
        members_payload.append(
            {
                "id": member.id,
                "full_name": member.full_name,
                "avg_score": score,
                "place": index + 1,
                "photo": member.photo.url if member.photo else "",
                "sport_category": member.sport_category.name
                if member.sport_category
                else None,
                "achievements": [
                    {"id": achievement.id, "name": achievement.name}
                    for achievement in member.achievements.all()[:5]
                ],
                "competition_results": competition_results.get(
                    member.user.id if member.user else None, []
                ),
            }
        )

    return {
        "team_avg": team_avg,
        "team_place": team_place,
        "team_total": len(company_customers),
        "members": members_payload,
    }


def get_company_group_ratings_data(
    custumer: Custumer, date=None
) -> Dict[str, Any]:
    if date is None:
        date = timezone.now().date()

    groups = list(
        GroupsClass.objects.filter(company_id=custumer.company_id)
        .order_by("position", "name", "id")
    )
    group_ids = [group.id for group in groups]
    week_start = date - timedelta(days=6)

    if not group_ids:
        return {"groups": [], "week_group": None}

    avg_case = Case(
        *(
            When(attendance_status=status, then=score)
            for status, score in ATTENDANCE_SCORE.items()
        ),
        output_field=IntegerField(),
    )
    all_time_rows = (
        GroupClassessCustumer.objects.filter(
            gr_class__groups_id__in=group_ids,
            attendance_status__in=ATTENDANCE_SCORE.keys(),
        )
        .values("gr_class__groups_id")
        .annotate(avg_score=Avg(avg_case))
    )
    week_rows = (
        GroupClassessCustumer.objects.filter(
            gr_class__groups_id__in=group_ids,
            date__gte=week_start,
            date__lte=date,
            attendance_status__in=ATTENDANCE_SCORE.keys(),
        )
        .values("gr_class__groups_id")
        .annotate(avg_score=Avg(avg_case))
    )
    all_time_avg = {
        row["gr_class__groups_id"]: round(row["avg_score"] or 0, 2)
        for row in all_time_rows
    }
    week_avg = {
        row["gr_class__groups_id"]: round(row["avg_score"] or 0, 2)
        for row in week_rows
    }

    ranked_groups = sorted(
        [
            {
                "id": group.id,
                "name": group.name,
                "average": all_time_avg.get(group.id, 0),
                "week_average": week_avg.get(group.id, 0),
            }
            for group in groups
        ],
        key=lambda item: (item["average"], item["week_average"]),
        reverse=True,
    )
    for index, group in enumerate(ranked_groups, start=1):
        group["place"] = index

    week_group = max(
        ranked_groups,
        key=lambda item: item["week_average"],
        default=None,
    )
    if week_group and week_group["week_average"] <= 0:
        week_group = None

    return {
        "groups": ranked_groups,
        "week_group": week_group,
    }


def get_news_data(custumer: Custumer, limit: int = 5) -> List[Dict[str, Any]]:
    if not custumer or not custumer.owner_id:
        return []

    news_items = (
        News.objects.filter(
            owner_id=custumer.owner_id, status=StatusTextChoices.PUBLISHED
        )
        .order_by("-created_at")[:limit]
        .select_related("owner")
    )

    return [
        {
            "id": item.id,
            "title": item.title,
            "created_at": item.created_at,
            "image": item.image.url if item.image else "",
            "description": item.descriptions or "",
        }
        for item in news_items
    ]


def get_trainings_today_data(
    custumer: Custumer, date=None
) -> List[Dict[str, Any]]:
    if date is None:
        date = timezone.now().date()

    groups = custumer.groups.all()

    trainings = (
        GroupClasses.objects.select_related("groups_id", "company")
        .filter(
            company_id=custumer.company_id, date=date, groups_id__in=groups
        )
        .order_by("strat")
    )

    return [
        {
            "id": training.id,
            "name": training.name,
            "group": training.groups_id.name if training.groups_id else "",
            "start": training.strat,
        }
        for training in trainings
    ]


def get_active_subscriptions_data(
    custumer: Custumer, date=None
) -> List[Dict[str, Any]]:
    if date is None:
        date = timezone.now().date()

    subscriptions = CustumerSubscription.objects.filter(
        custumer_id=custumer.id,
        start_date__lte=date,
        end_date__gte=date,
        is_blok=False,
    ).order_by("-end_date")

    payload: List[Dict[str, Any]] = []
    for subscription in subscriptions:
        percent = 0
        if not subscription.unlimited and subscription.number_classes:
            remained = subscription.remained or 0
            percent = (
                (remained / subscription.number_classes) * 100
                if subscription.number_classes
                else 0
            )

        payload.append(
            {
                "id": subscription.id,
                "unlimited": subscription.unlimited,
                "remained": subscription.remained,
                "number_classes": subscription.number_classes,
                "days_left": subscription.days_left,
                "end_date": subscription.end_date,
                "percent_used": round(percent, 2),
            }
        )

    return payload


def get_distance_summary(custumer: Custumer, date=None) -> DistanceSummary:
    if date is None:
        date = timezone.now().date()

    week_ago = date - timedelta(days=7)
    year_ago = date - timedelta(days=365)
    competition_distances = (
        CustumerCompetitionResult.objects.filter(
            customer_id=custumer.id,
            competition__date__gte=year_ago,
            competition__date__lte=date,
        )
        .values("competition__date")
        .annotate(total_distance=Sum("distance"))
    )

    distance_week, distance_year = 0.0, 0.0
    for result in competition_distances:
        total = result["total_distance"] or 0
        if result["competition__date"] >= week_ago:
            distance_week += total
        distance_year += total

    program_week, program_year = get_client_distances(custumer, date)
    return DistanceSummary(
        week=round(distance_week / 1000, 2) + program_week,
        year=round(distance_year / 1000, 2) + program_year,
    )


def get_group_modal_data(custumer: Custumer) -> Dict[str, Any]:
    ratings_data = get_group_ratings_data(custumer)
    return {
        "group_ratings": ratings_data["groups"],
        "best_group": ratings_data["best_group"],
    }
