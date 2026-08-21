"""Translate `attr_*` query parameters into ORM filters.

The search bar is generated from the `*_search_attributes` tables, so the set of
filters is not known at build time. Rather than inventing a new query language,
each dynamic filter arrives as a conventionally named parameter:

    ?attr_parking=true                  boolean / exact
    ?attr_document_type=single_deed     select
    ?attr_total_floors_min=5            numeric range
    ?attr_total_floors_max=20
    ?attr_handover_min=2026-01-01       date range

Values are matched against the *typed* EAV column for the attribute, so a
numeric comparison stays numeric — filtering `>= 5` cannot accidentally compare
strings and rank "9" above "20".

Core attributes are handled here too: they map to a real column on the model, so
they filter directly rather than through the EAV join.
"""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Q

PREFIX = "attr_"
MIN_SUFFIX = "_min"
MAX_SUFFIX = "_max"

# Tokens accepted for a boolean attribute, matching the EAV writer.
TRUE_TOKENS = {"true", "1", "yes", "on", "بله"}
FALSE_TOKENS = {"false", "0", "no", "off", "خیر"}


def _coerce(attribute, raw: str):
    """Parse ``raw`` into the Python type the attribute stores.

    Returns ``None`` when the value cannot be parsed, so a malformed filter is
    ignored rather than raising: a stray query string should not turn the whole
    listing page into a 500.
    """
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

    # text / select / multiselect all compare as text
    return token


def _value_column(attribute) -> str:
    """The typed EAV column this attribute's values live in."""
    return attribute.value_field


def parse_attribute_filters(query_params) -> dict[str, dict]:
    """Group `attr_*` parameters by attribute name.

    Returns ``{name: {"exact": v, "min": v, "max": v}}`` with only the keys
    that were supplied.
    """
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
    """Narrow ``queryset`` by every recognised `attr_*` parameter.

    ``entity``          – Attribute.Entity.PROPERTY or .LISTING
    ``values_relation`` – reverse accessor to the EAV rows, e.g.
                          "attribute_values"

    Unknown attribute names and unparseable values are ignored, so a stale
    bookmark degrades to a broader result set instead of an error.
    """
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

        # --- core attributes map to a real column ---------------------------
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

        # --- dynamic attributes go through the typed EAV column -------------
        column = _value_column(attribute)
        conditions = Q(**{f"{values_relation}__attribute": attribute})
        matched = False

        if "exact" in bounds:
            value = _coerce(attribute, bounds["exact"])
            if value is not None:
                if attribute.data_type == Attribute.DataType.MULTISELECT:
                    # A multiselect stores a JSON list; "contains" asks whether
                    # the chosen option is among the selected ones.
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
            # Each attribute is a separate filter() call so the conditions apply
            # to the *same* related row. Combining them into one call would let
            # two different attributes satisfy one clause each.
            queryset = queryset.filter(conditions)

    return queryset.distinct()
