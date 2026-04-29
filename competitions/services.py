from collections import defaultdict

from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404

from base.cache_utils import get_cached_sport_categories
from competitions.models import Competitions, CustumerCompetitionResult
from competitions.schemas import StyleTextChoices
from custumer.models import Custumer, SportCategory


class CompetitionResultError(ValueError):
    pass


def parse_competition_result_payload(payload):
    distance = str(payload.get("distance", "")).strip()
    discipline = str(payload.get("discipline", "")).strip()
    style = str(payload.get("style", "")).strip()
    result_time = str(payload.get("result_time", "")).strip()
    place = str(payload.get("place", "")).strip()
    assign_rank = str(payload.get("assign_rank", "")).strip()
    disqualification_comment = str(
        payload.get("disqualification_comment", "")
    ).strip()
    is_disqualified = payload.get("is_disqualified") in (
        True,
        "true",
        "True",
        "1",
        "on",
    )

    try:
        distance_val = float(distance)
        if distance_val <= 0:
            raise ValueError
    except ValueError as exc:
        raise CompetitionResultError(
            "Distance must be a positive number."
        ) from exc

    time_ms = None
    place_val = None

    if not is_disqualified:
        if not result_time:
            raise CompetitionResultError(
                "Time is required for non-disqualified participants."
            )

        try:
            parts = result_time.split(":")
            if len(parts) != 3:
                raise ValueError("invalid format")

            minutes = int(parts[0])
            seconds = int(parts[1])
            milliseconds = int(parts[2])

            if not (0 <= minutes <= 99):
                raise ValueError("minutes must be from 0 to 99")
            if not (0 <= seconds <= 59):
                raise ValueError("seconds must be from 0 to 59")
            if not (0 <= milliseconds <= 999):
                raise ValueError("milliseconds must be from 0 to 999")

            time_ms = (minutes * 60 + seconds) * 1000 + milliseconds
            if time_ms <= 0:
                raise ValueError("time must be greater than zero")
        except (ValueError, IndexError) as exc:
            raise CompetitionResultError(
                f"Time must be in mm:ss:ms format. {exc}"
            ) from exc

        if not place:
            raise CompetitionResultError(
                "Place is required for non-disqualified participants."
            )

        try:
            place_val = int(place)
            if place_val < 1:
                raise ValueError
        except ValueError as exc:
            raise CompetitionResultError(
                "Place must be a positive integer."
            ) from exc
    elif not disqualification_comment:
        raise CompetitionResultError(
            "Disqualification comment is required."
        )

    return {
        "distance": distance_val,
        "discipline": discipline,
        "style": style,
        "result_time_ms": time_ms,
        "place": place_val,
        "assign_rank": assign_rank,
        "is_disqualified": is_disqualified,
        "disqualification_comment": disqualification_comment,
    }


def get_assigned_sport_category(assign_rank):
    if not assign_rank or assign_rank == "0":
        return None

    try:
        return SportCategory.objects.get(id=assign_rank)
    except SportCategory.DoesNotExist as exc:
        raise CompetitionResultError("Sport category not found.") from exc


def apply_rank_to_customer(customer, sport_category, result=None):
    if not sport_category:
        return None

    from competitions.utils import assign_rank_to_customer

    success, message, _ = assign_rank_to_customer(
        customer,
        sport_category,
        result,
    )
    if not success:
        raise CompetitionResultError(message)
    return message


def create_competition_result(competition, customer, payload):
    data = parse_competition_result_payload(payload)
    sport_category = get_assigned_sport_category(data.pop("assign_rank"))
    rank_message = apply_rank_to_customer(customer, sport_category)

    result = CustumerCompetitionResult.objects.create(
        competition=competition,
        customer=customer,
        sport_category=sport_category,
        **data,
    )
    return result, rank_message


def update_competition_result_instance(result, payload):
    data = parse_competition_result_payload(payload)
    sport_category = get_assigned_sport_category(data.pop("assign_rank"))
    rank_message = apply_rank_to_customer(
        result.customer,
        sport_category,
        result,
    )

    result.distance = data["distance"]
    result.discipline = data["discipline"]
    result.style = data["style"]
    result.result_time_ms = data["result_time_ms"]
    result.place = data["place"]
    result.is_disqualified = data["is_disqualified"]
    result.disqualification_comment = data["disqualification_comment"]
    result.sport_category = sport_category
    result.save()
    return result, rank_message


def get_competition_context(competition_id, user):
    """
    Подготавливает данные для страницы деталей соревнования.

    Возвращает словарь с объектом соревнования (с заранее
    подгруженными участниками), списком клиентов компании
    и справочными данными.
    """
    company_customers_qs = (
        Custumer.objects.filter(company=user.company)
        .select_related("sport_category")
        .prefetch_related("groups")
        .order_by("full_name")
    )

    competition_qs = (
        Competitions.objects.select_related("owner")
        .prefetch_related(
            Prefetch(
                "customers",
                queryset=company_customers_qs,
                to_attr="prefetched_customers",
            )
        )
        .filter(owner__company=user.company)
    )

    competition = get_object_or_404(competition_qs, id=competition_id)
    competition_customers = getattr(competition, "prefetched_customers", [])

    return {
        "competition": competition,
        "competition_customers": competition_customers,
        "competition_customer_ids": [
            customer.id for customer in competition_customers
        ],
        "all_customers": company_customers_qs,
        "status_choices": Competitions._meta.get_field("status").choices,
        "sport_categories": get_cached_sport_categories(),
        "style_choices": StyleTextChoices.choices,
    }


def get_competition_results_data(competition_id, user):
    """
    Возвращает агрегированные данные по результатам соревнования
    для асинхронной загрузки на клиенте.
    """
    participants = (
        Custumer.objects.filter(
            competitions__id=competition_id, company=user.company
        )
        .select_related("sport_category")
        .prefetch_related("groups")
        .distinct()
    )

    participant_map = {
        participant.id: {
            "id": participant.id,
            "name": participant.full_name,
            "phone": participant.phone or "",
            "rank": participant.sport_category.name
            if participant.sport_category
            else None,
        }
        for participant in participants
    }

    results_qs = (
        CustumerCompetitionResult.objects.select_related("sport_category")
        .filter(competition_id=competition_id)
        .order_by(
            "is_disqualified",
            F("place").asc(nulls_last=True),
            "distance",
            "style",
        )
    )

    grouped_results = defaultdict(list)
    for result in results_qs:
        grouped_results[result.customer.id].append(
            {
                "id": result.id,
                "distance": result.distance,
                "discipline": result.discipline or "",
                "style": result.get_style_display or "",
                "result_time": result.format_time(),
                "place": result.place,
                "is_disqualified": result.is_disqualified,
                "disqualification_comment": result.disqualification_comment
                or "",
                "sport_category": result.sport_category.name
                if result.sport_category
                else None,
            }
        )

    payload = []
    for participant_id, participant_data in participant_map.items():
        payload.append(
            {
                "participant": participant_data,
                "results": grouped_results.get(participant_id, []),
            }
        )

    def _participant_sort_key(entry):
        results = entry["results"]
        if results:
            valid_places = [
                r["place"]
                for r in results
                if r["place"] is not None and not r["is_disqualified"]
            ]
            if valid_places:
                return (0, min(valid_places))
            return (1, entry["participant"]["name"])
        return (2, entry["participant"]["name"])

    payload.sort(key=_participant_sort_key)

    return payload
