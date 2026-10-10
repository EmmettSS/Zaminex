import difflib
import unicodedata
from functools import lru_cache

from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.db.models import (
    AutoField,
    BigAutoField,
    BigIntegerField,
    Case,
    CharField,
    DecimalField,
    F,
    FloatField,
    Func,
    IntegerField,
    PositiveIntegerField,
    Q,
    SmallAutoField,
    SmallIntegerField,
    TextField,
    Value,
    When,
)
from django.db.models.functions import Greatest, Replace, Upper
from django.db.models.lookups import Lookup

_NUMERIC_FIELD_TYPES = (
    AutoField,
    BigAutoField,
    SmallAutoField,
    IntegerField,
    BigIntegerField,
    SmallIntegerField,
    PositiveIntegerField,
    DecimalField,
    FloatField,
)


def _is_numeric_lookup(model, field_path: str) -> bool:
    current = model
    parts = str(field_path).split("__")
    for i, name in enumerate(parts):
        try:
            field = current._meta.get_field(name)
        except FieldDoesNotExist:
            return False
        if getattr(field, "is_relation", False):
            if i == len(parts) - 1:
                return True
            current = field.related_model
            if current is None:
                return False
            continue
        return isinstance(field, _NUMERIC_FIELD_TYPES)
    return False


def _is_code_lookup(model, field_path: str) -> bool:
    return str(field_path).split("__")[-1] == "internal_code"


def _split_search_fields(queryset, fields):
    text_fields = []
    numeric_fields = []
    code_fields = []
    model = queryset.model
    for field in fields:
        if _is_code_lookup(model, field):
            code_fields.append(field)
        elif _is_numeric_lookup(model, field):
            numeric_fields.append(field)
        else:
            text_fields.append(field)
    return text_fields, numeric_fields, code_fields


def _match_q(queryset, query, fields):
    text_fields, numeric_fields, code_fields = _split_search_fields(queryset, fields)
    q_obj = Q()
    for field in text_fields:
        q_obj |= Q(**{f"{field}__icontains": query})
    for field in code_fields:
        q_obj |= Q(**{f"{field}__istartswith": query})
    if str(query).isdigit():
        as_int = int(query)
        for field in numeric_fields:
            q_obj |= Q(**{field: as_int})
    return q_obj, text_fields, numeric_fields, code_fields

FUZZY_SEARCH_THRESHOLD = 0.45

_DIGIT_TRANSLATION = str.maketrans(
    {
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
        "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    }
)

_LETTER_TRANSLATION = str.maketrans(
    {
        "\u064a": "\u06cc",
        "\u0649": "\u06cc",
        "\u0643": "\u06a9",
        "\u0629": "\u0647",
    }
)


def normalize_persian_text(value) -> str:
    if not value:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = text.translate(_LETTER_TRANSLATION)
    text = text.translate(_DIGIT_TRANSLATION)
    text = text.replace("\u200c", "")
    return " ".join(text.split())


def _pg_trgm_available() -> bool:
    if getattr(connection, "vendor", "") != "postgresql":
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT show_trgm(%s)", ["آپارتمان"])
            row = cursor.fetchone()
            return bool(row and row[0])
    except Exception:
        return False


class _WordMatchSimilarity(Func):
    function = "word_similarity"
    output_field = FloatField()


class _ReversedWordSimilarGate(Lookup):
    lookup_name = "word_similar_gate"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        
        return f"{rhs} <%% {lhs}", [*rhs_params, *lhs_params]


for _field_class in (CharField, TextField):
    _field_class.register_lookup(_ReversedWordSimilarGate)


def _set_trgm_gate(threshold: float) -> float:
    gate = max(0.05, round(threshold - 0.01, 4))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('pg_trgm.word_similarity_threshold', %s, false),"
            "       set_config('pg_trgm.similarity_threshold', %s, false)",
            [str(gate), str(gate)],
        )
    return gate


def _stripped_field(field: str):
    return Replace(F(field), Value("\u200c"), Value(""), output_field=TextField())


def _index_expression(field: str):
    return Upper(_stripped_field(field))


@lru_cache(maxsize=16384)
def _token_ratio(a: str, b: str) -> float:
    total = len(a) + len(b)
    if total and 2 * min(len(a), len(b)) < 0.70 * total:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _score_ordering(scored):
    buckets = {}
    for position, (_, score) in enumerate(scored):
        buckets.setdefault(score, []).append(position)
    return Case(
        *[
            When(pk__in=[scored[position][0] for position in positions], then=rank)
            for rank, positions in enumerate(buckets.values())
        ],
        output_field=IntegerField(),
    )


def apply_fuzzy_search(queryset, query, fields, threshold=FUZZY_SEARCH_THRESHOLD):
    query = (query or "").strip()
    if not query:
        return queryset

    normalized_query = normalize_persian_text(query)
    if not normalized_query:
        return queryset

    base_q, text_fields, numeric_fields, code_fields = _match_q(
        queryset, normalized_query, fields
    )
    if query != normalized_query:
        raw_q, _, _, _ = _match_q(queryset, query, fields)
        base_q |= raw_q

    if not text_fields and not code_fields and not (
        normalized_query.isdigit() and numeric_fields
    ):
        return queryset.none()

    if _pg_trgm_available() and text_fields:
        min_thresh = (
            threshold
            if isinstance(threshold, float) and 0 < threshold <= 1.0
            else FUZZY_SEARCH_THRESHOLD
        )
        multi_word = " " in normalized_query

        qs = queryset
        aliases = {}
        for position, field in enumerate(text_fields + code_fields):
            alias = f"_stripped{position}"
            aliases[field] = alias
            qs = qs.annotate(**{alias: _index_expression(field)})

        if multi_word:
            from django.contrib.postgres.search import TrigramSimilarity

            sim_exprs = [
                TrigramSimilarity(_index_expression(field), normalized_query)
                for field in text_fields
            ]
        else:
            sim_exprs = [
                _WordMatchSimilarity(
                    Value(normalized_query), _index_expression(field)
                )
                for field in text_fields
            ]
        max_sim_expr = sim_exprs[0] if len(sim_exprs) == 1 else Greatest(*sim_exprs)
        qs = qs.annotate(_search_sim=max_sim_expr)

        _set_trgm_gate(min_thresh)
        gate_q = Q()
        for field in text_fields:
            alias = aliases[field]
            if multi_word:
                gate_q |= Q(**{f"{alias}__trigram_similar": normalized_query})
            else:
                gate_q |= Q(**{f"{alias}__word_similar_gate": normalized_query})

        def _exact_match_q(search_text):
            pattern = str(search_text).upper()
            q = Q()
            for field in text_fields:
                q |= Q(**{f"{aliases[field]}__contains": pattern})
            for field in code_fields:
                q |= Q(**{f"{aliases[field]}__startswith": pattern})
            if str(search_text).isdigit():
                as_int = int(search_text)
                for field in numeric_fields:
                    q |= Q(**{field: as_int})
            return q

        exact_q = _exact_match_q(normalized_query)
        if query != normalized_query:
            exact_q |= _exact_match_q(query)

        qs = qs.filter(exact_q | gate_q)
        qs = qs.filter(exact_q | Q(_search_sim__gte=min_thresh))

        return qs.order_by("-_search_sim", "-id")

    else:
        filtered_qs = queryset.filter(base_q)
        if filtered_qs.exists():
            return filtered_qs

        terms = normalized_query.split()
        if len(terms) > 1:
            term_q = Q()
            for term in terms:
                sub_q = Q()
                for field in text_fields:
                    sub_q |= Q(**{f"{field}__icontains": term})
                if term.isdigit():
                    as_int = int(term)
                    for field in numeric_fields:
                        sub_q |= Q(**{field: as_int})
                term_q &= sub_q
            multi_matched = queryset.filter(term_q)
            if multi_matched.exists():
                return multi_matched

        rows = list(queryset.values_list("pk", *text_fields))
        scored = []

        q_len = len(normalized_query)
        q_trigrams = set(normalized_query[i:i+3] for i in range(max(1, q_len - 2)))
        q_tokens = normalized_query.split()

        for row in rows:
            pk = row[0]
            max_score = 0.0
            for val in row[1:]:
                if val is None:
                    continue
                norm_val = normalize_persian_text(val)
                if not norm_val:
                    continue

                if normalized_query in norm_val:
                    max_score = max(max_score, 1.0)
                    break

                v_trigrams = set(norm_val[i:i+3] for i in range(max(1, len(norm_val) - 2)))
                if q_trigrams and v_trigrams:
                    sim = len(q_trigrams & v_trigrams) / float(len(q_trigrams | v_trigrams))
                    if sim > max_score:
                        max_score = sim

                v_tokens = norm_val.split()
                for q_tok in q_tokens:
                    for v_tok in v_tokens:
                        seq_ratio = _token_ratio(q_tok, v_tok)
                        if seq_ratio >= 0.70:
                            max_score = max(max_score, seq_ratio)

            if max_score >= 0.15:
                scored.append((pk, max_score))

        if not scored:
            return queryset.none()

        scored.sort(key=lambda x: x[1], reverse=True)
        matched_pks = [pk for pk, _ in scored]

        return queryset.filter(pk__in=matched_pks).order_by(
            _score_ordering(scored), "-id"
        )
