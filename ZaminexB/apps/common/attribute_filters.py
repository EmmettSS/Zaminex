from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Q

PREFIX = "attr_"
MIN_SUFFIX = "_min"
MAX_SUFFIX = "_max"

TRUE_TOKENS = {"true", "1", "yes", "on", "بله"}
FALSE_TOKENS = {"false", "0", "no", "off", "خیر"}


def _coerce(attribute, raw: str):
    from apps.basics.models import Attribute

    data_type = attribute.data_type
    token = (raw or "").strip()
    if not token:
        return None

    if data_type == Attribute.DataType.INTEGER:
        try:
            return int(token.replace(",", ""))
        except (TypeError, ValueError):
            return None

    if data_type == Attribute.DataType.DECIMAL:
        try:
            return Decimal(token.replace(",", ""))
        except (TypeError, ValueError, InvalidOperation):
            return None

    if data_type == Attribute.DataType.BOOLEAN:
        lowered = token.lower()
        if lowered in TRUE_TOKENS:
            return True
        if lowered in FALSE_TOKENS:
            return False
        return None

    if data_type == Attribute.DataType.DATE:
        try:
            return datetime.date.fromisoformat(token)
        except (TypeError, ValueError):
            return None

    return token


def _value_column(attribute) -> str:
    return attribute.value_field


def parse_attribute_filters(query_params) -> dict[str, dict]:
    parsed: dict[str, dict] = {}

    for key, value in query_params.items():
        if not key.startswith(PREFIX) or value in (None, ""):
            continue
        remainder = key[len(PREFIX):]

        if remainder.endswith(MIN_SUFFIX):
            parsed.setdefault(remainder[: -len(MIN_SUFFIX)], {})["min"] = value
        elif remainder.endswith(MAX_SUFFIX):
            parsed.setdefault(remainder[: -len(MAX_SUFFIX)], {})["max"] = value
        else:
            parsed.setdefault(remainder, {})["exact"] = value

    return parsed


def apply_attribute_filters(queryset, query_params, *, entity, values_relation):
    from apps.basics.models import Attribute

    requested = parse_attribute_filters(query_params)
    if not requested:
        return queryset

    attributes = {
        attribute.name: attribute
        for attribute in Attribute.objects.filter(
            name__in=list(requested), entity=entity
        )
    }

    for name, bounds in requested.items():
        attribute = attributes.get(name)
        if attribute is None:
            continue

        if attribute.is_core and attribute.core_field:
            field = attribute.core_field
            if "exact" in bounds:
                value = _coerce(attribute, bounds["exact"])
                if value is not None:
                    queryset = queryset.filter(**{field: value})
            if "min" in bounds:
                value = _coerce(attribute, bounds["min"])
                if value is not None:
                    queryset = queryset.filter(**{f"{field}__gte": value})
            if "max" in bounds:
                value = _coerce(attribute, bounds["max"])
                if value is not None:
                    queryset = queryset.filter(**{f"{field}__lte": value})
            continue

        column = _value_column(attribute)
        conditions = Q(**{f"{values_relation}__attribute": attribute})
        matched = False

        if "exact" in bounds:
            value = _coerce(attribute, bounds["exact"])
            if value is not None:
                if attribute.data_type == Attribute.DataType.MULTISELECT:
                    conditions &= Q(
                        **{f"{values_relation}__{column}__contains": [value]}
                    )
                else:
                    conditions &= Q(**{f"{values_relation}__{column}": value})
                matched = True

        if "min" in bounds:
            value = _coerce(attribute, bounds["min"])
            if value is not None:
                conditions &= Q(**{f"{values_relation}__{column}__gte": value})
                matched = True

        if "max" in bounds:
            value = _coerce(attribute, bounds["max"])
            if value is not None:
                conditions &= Q(**{f"{values_relation}__{column}__lte": value})
                matched = True

        if matched:
            queryset = queryset.filter(conditions)

    return queryset.distinct()
