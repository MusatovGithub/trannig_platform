from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Sequence

from django.core.exceptions import ValidationError

from authen.models import CustomUser, Gender
from custumer.models import Custumer, SportCategory
from groups_custumer.models import GroupsClass

DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")
DEFAULT_SPORT_CATEGORY_ID = 8


@dataclass(frozen=True)
class CustomerServiceResult:
    customer: Custumer
    group_ids: List[int]


def create_customer(
    *,
    owner: CustomUser,
    data: dict,
    photo=None,
) -> CustomerServiceResult:
    customer = Custumer(owner=owner, company=owner.company)
    return _save_customer(
        customer=customer,
        owner=owner,
        data=data,
        photo=photo,
        force_group_update=False,
        group_scope="owner",
    )


def update_customer(
    *,
    customer: Custumer,
    owner: CustomUser,
    data: dict,
    photo=None,
) -> CustomerServiceResult:
    return _save_customer(
        customer=customer,
        owner=owner,
        data=data,
        photo=photo,
        force_group_update=True,
        group_scope="any",
    )


def _save_customer(
    *,
    customer: Custumer,
    owner: CustomUser,
    data: dict,
    photo,
    force_group_update: bool,
    group_scope: str,
) -> CustomerServiceResult:
    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        raise ValidationError("Требуется Ф.И.О.")

    gender = _resolve_gender(data.get("gender"))
    sport_category = _resolve_sport_category(
        data.get("sport_rank") or DEFAULT_SPORT_CATEGORY_ID
    )

    birth_date = _parse_optional_date(data.get("birth_date"), "дата рождения")
    start_date = _parse_optional_date(
        data.get("start_date"), "дата начала обучения"
    )

    customer.full_name = full_name
    customer.phone = data.get("phone") or None
    customer.gender = gender
    customer.birth_date = birth_date
    customer.address = data.get("address") or None
    customer.contract_number = data.get("contract_number") or None
    customer.contract_type = data.get("contract_type") or None
    customer.strat_date = start_date
    customer.sport_category = sport_category
    customer.company = owner.company
    customer.owner = owner

    if photo is not None:
        customer.photo = photo

    customer.save()

    group_ids = data.get("group_ids")
    groups_qs = _resolve_groups(
        group_ids=group_ids,
        owner=owner,
        scope=group_scope,
    )

    if group_ids is not None and (force_group_update or group_ids):
        customer.groups.set(groups_qs)

    assigned_group_ids = list(customer.groups.values_list("id", flat=True))
    return CustomerServiceResult(
        customer=customer,
        group_ids=assigned_group_ids,
    )


def _resolve_gender(gender_id):
    if not gender_id:
        return None
    try:
        return Gender.objects.get(id=gender_id)
    except Gender.DoesNotExist as exc:
        raise ValidationError("Указан неверный пол") from exc


def _resolve_sport_category(sport_category_id):
    if not sport_category_id:
        return None
    return SportCategory.objects.filter(id=sport_category_id).first()


def _parse_optional_date(value: str | None, field_name: str):
    if not value:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValidationError(
        f"Неверный формат для '{field_name}'. "
        f"Ожидается один из форматов: {', '.join(DATE_FORMATS)}"
    )


def _resolve_groups(
    *,
    group_ids: Sequence[str] | None,
    owner: CustomUser,
    scope: str,
) -> Iterable[GroupsClass]:
    if not group_ids:
        return GroupsClass.objects.none()

    queryset = GroupsClass.objects.filter(id__in=group_ids)
    if scope == "owner":
        queryset = queryset.filter(owner_id=owner)
    elif scope == "company":
        queryset = queryset.filter(company=owner.company)
    return queryset
