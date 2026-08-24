"""
Shared search helper for the Zaminex backend.

This module is the single server-side gateway for search. Every list
endpoint that accepts free-text user input (the `?q=` parameters on
properties and listings, and the non-numeric name fallback filters) routes
through ``apply_fuzzy_search`` so no view ever re-implements its own matching.

Matching rules (PostgreSQL + pg_trgm):
  * exact substrings always match (icontains) — the primary precision path;
  * typo tolerance is shape-aware:
      - a single-word query is scored with ``word_similarity(query, field)``:
        it must line up with a real word inside the field, keeping genuine
        typos (مشاهر → مشاور) while rejecting cross-word trigram noise
        (خواب → می‌خواهم, نیاوران → تهران);
      - a multi-word query is a phrase, scored with plain ``similarity``
        over the whole field: «اپارتمان لوکس» matches «فروش آپارتمان لوکس»
        without leaking into fields that only share one word;
  * the field side has ZWNJ stripped first so compounds like «می‌خواهم» are
    scored as one word instead of two;
  * internal codes match by exact prefix only — they are identifiers, so a
    fuzzy match must never silently surface a different code;
  * equal relevance scores fall back to newest-id first, so pagination is
    deterministic and can never skip or repeat rows.

On non-PostgreSQL backends a portable Python fallback provides the same
Persian normalization and typo tolerance.
"""

import difflib
import unicodedata

from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.db.models import (
    AutoField,
    BigAutoField,
    BigIntegerField,
    Case,
    DecimalField,
    F,
    FloatField,
    Func,
    IntegerField,
    PositiveIntegerField,
    Q,
    SmallAutoField,
    SmallIntegerField,
    Value,
    When,
)
from django.db.models.functions import Greatest, Replace

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
    """True when ``field_path`` resolves to a numeric column (or a bare FK).

    Trigram similarity and ``__icontains`` are text operations. Applying them
    to an integer PK (e.g. listing ``id``) 500s on PostgreSQL and can empty
    the listings/properties search results on the frontend.
    """
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
    """True when the field holds an internal identifier (کد داخلی).

    Codes are identifiers, not prose. A fuzzy match must never silently
    surface a different code («LC-1» → «LC-2»): codes match by exact prefix
    only and are excluded from trigram similarity.
    """
    return str(field_path).split("__")[-1] == "internal_code"


def _split_search_fields(queryset, fields):
    """Bucket the searched fields by how they may match the query."""
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
    """Build a Q that is safe for text, code and numeric lookups.

    Text fields match by normalized substring (the precision path), codes by
    exact prefix (identifier semantics), and numeric fields by exact value
    when the query itself is a number.
    """
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

# Similarity threshold for the pg_trgm path. Measured against the Persian
# test corpus:
#   * single-word typos score ≥ 0.5 (ویا→ویلا، مشاهر→مشاور،
#     اپارتمان→آپارتمان) while cross-word noise stays ≤ 0.4
#     (خواب→می‌خواهم 0.2، نیاوران→تهران 0.25، کافه→دفتر کار مرکزی 0.4);
#   * multi-word phrases: matches ≥ 0.5 (اپارتمان لوکس→فروش آپارتمان لوکس)
#     and noise ≤ 0.35 (آپارتمان تست صفحه→آپارتمان دو خواب).
# 0.45 separates both groups with a margin on both sides.
FUZZY_SEARCH_THRESHOLD = 0.45

# Unify Persian (۰-۹) and Arabic-Indic (٠-٩) digits to ASCII. This mirrors the
# frontend pipeline and makes `internal_code` searches tolerant of Persian
# digits typed into a Persian keyboard layout.
_DIGIT_TRANSLATION = str.maketrans(
    {
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
        "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    }
)

# Arabic letter variants that differ from their Persian equivalents but are
# commonly typed in place of them (e.g. an Arabic keyboard layout).
_LETTER_TRANSLATION = str.maketrans(
    {
        "\u064a": "\u06cc",  # Arabic ye          -> Persian ye
        "\u0649": "\u06cc",  # Arabic alef maksura -> Persian ye
        "\u0643": "\u06a9",  # Arabic kaf         -> Persian kaf
        "\u0629": "\u0647",  # Arabic ta marbuta  -> Persian he
    }
)


def normalize_persian_text(value) -> str:
    """Persian-safe normalization, mirroring the frontend pipeline.

    Applies NFC composition, case folding, Arabic-to-Persian letter
    unification, digit unification, ZWNJ removal, whitespace collapse and
    trimming. Returns ``""`` for ``None``/empty input.
    """
    if not value:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = text.translate(_LETTER_TRANSLATION)
    text = text.translate(_DIGIT_TRANSLATION)
    text = text.replace("\u200c", "")  # zero-width non-joiner
    return " ".join(text.split())


def _pg_trgm_available() -> bool:
    """Whether the pg_trgm extension is installed on the connected PostgreSQL.

    The trigram path depends on the `pg_trgm` extension; on a database where it
    is missing (e.g. an existing install that predates the enabling migration)
    the similarity() function does not exist and every search would 500. We
    detect it lazily and fall back to the portable fuzzy path instead.
    """
    if getattr(connection, "vendor", "") != "postgresql":
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
            )
            return cursor.fetchone() is not None
    except Exception:
        return False


class _WordMatchSimilarity(Func):
    """``word_similarity(query, field)`` with the query FIRST.

    Django's built-in ``TrigramWordSimilarity`` fixes the argument order as
    ``(field, query)``. Swapping it changes the semantics to what search
    actually needs: pg_trgm then compares the query against its best
    *word-aligned extent* inside the field, so a typo only matches when it
    lines up with a real word of the field («مشاهر» matches «مشاور» inside
    «مرکز مشاور املاک») instead of leaking across unrelated word fragments.
    """

    function = "word_similarity"
    output_field = FloatField()


def _stripped_field(field: str):
    """The field expression with ZWNJ removed.

    pg_trgm treats the zero-width non-joiner as a word separator, which
    splits compounds like «می‌خواهم» into «می» + «خواهم» and lets noise
    through («خواب» then matches «خواهم»). Comparing against the
    ZWNJ-stripped text restores the true word.
    """
    return Replace(F(field), Value("\u200c"), Value(""))


def apply_fuzzy_search(queryset, query, fields, threshold=FUZZY_SEARCH_THRESHOLD):
    """Restrict ``queryset`` to rows matching ``query`` on ``fields``.

    On PostgreSQL this uses pg_trgm word-aligned similarity for typo
    tolerance plus exact substring/code/numeric matching; on other backends
    a portable Python fallback provides the same Persian normalization and
    typo tolerance.
    """
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
        # Scoring depends on the query shape:
        #   * a single word matches the best WORD-ALIGNED extent of the
        #     field (word_similarity with the query first) — «مشاهر» lines up
        #     with «مشاور» inside «مرکز مشاور املاک», while cross-word noise
        #     («خواب» vs «می‌خواهم») is rejected;
        #   * a multi-word query is a phrase, so the WHOLE phrase is scored
        #     against the field (plain similarity) — «اپارتمان لوکس» matches
        #     «فروش آپارتمان لوکس», while «آپارتمان تست صفحه» does not leak
        #     into «آپارتمان دو خواب» or «اپارتمان».
        if " " in normalized_query:
            from django.contrib.postgres.search import TrigramSimilarity

            sim_exprs = [
                # similarity() is symmetric, so the field-first argument
                # order of Django's class is fine here.
                TrigramSimilarity(_stripped_field(field), normalized_query)
                for field in text_fields
            ]
        else:
            sim_exprs = [
                _WordMatchSimilarity(Value(normalized_query), _stripped_field(field))
                for field in text_fields
            ]
        max_sim_expr = sim_exprs[0] if len(sim_exprs) == 1 else Greatest(*sim_exprs)

        qs = queryset.annotate(_search_sim=max_sim_expr)

        min_thresh = (
            threshold
            if isinstance(threshold, float) and 0 < threshold <= 1.0
            else FUZZY_SEARCH_THRESHOLD
        )

        qs = qs.filter(base_q | Q(_search_sim__gte=min_thresh))
        # Deterministic tie-breaker: equal relevance scores order by newest
        # id first, so pagination can never skip or repeat rows.
        return qs.order_by("-_search_sim", "-id")

    else:
        # Fallback for non-PostgreSQL backends.
        # 1. First attempt exact/substring/code/numeric filter
        filtered_qs = queryset.filter(base_q)
        if filtered_qs.exists():
            return filtered_qs

        # 2. Split multi-word query terms
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

        # 3. Python character sequence & trigram similarity fallback for typos
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

                # Trigram similarity
                v_trigrams = set(norm_val[i:i+3] for i in range(max(1, len(norm_val) - 2)))
                if q_trigrams and v_trigrams:
                    sim = len(q_trigrams & v_trigrams) / float(len(q_trigrams | v_trigrams))
                    if sim > max_score:
                        max_score = sim

                # Token-level sequence matcher for typos (e.g. "مشاهر" vs "مشاور")
                v_tokens = norm_val.split()
                for q_tok in q_tokens:
                    for v_tok in v_tokens:
                        seq_ratio = difflib.SequenceMatcher(None, q_tok, v_tok).ratio()
                        if seq_ratio >= 0.70:
                            max_score = max(max_score, seq_ratio)

            if max_score >= 0.15:
                scored.append((pk, max_score))

        if not scored:
            return queryset.none()

        scored.sort(key=lambda x: x[1], reverse=True)
        matched_pks = [pk for pk, _ in scored]

        ordering = Case(
            *[When(pk=pk, then=pos) for pos, pk in enumerate(matched_pks)],
            output_field=IntegerField(),
        )
        return queryset.filter(pk__in=matched_pks).order_by(ordering)
