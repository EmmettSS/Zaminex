import math

from django.core.paginator import Page
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.common import cache_utils


class _ServedCountPaginator:
    def __init__(self, per_page, served_count):
        self.per_page = per_page
        self._served_count = served_count

    @property
    def count(self):
        return self._served_count

    @property
    def num_pages(self):
        if self._served_count <= 0:
            return 1
        return max(1, math.ceil(self._served_count / self.per_page))

    def validate_number(self, number):
        if number < 1:
            return 1
        if number > self.num_pages:
            return self.num_pages
        return number


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    count_cache_ttl = 30

    def _count_key(self, request):
        params = request.query_params.copy()
        params.pop(self.page_query_param, None)
        params.pop(self.page_size_query_param, None)
        return cache_utils.make_key(
            "count",
            getattr(request.user, "pk", None) or "anon",
            request.path,
            params.urlencode(),
        )

    def _served_count(self, queryset, request):
        ttl = self.count_cache_ttl
        if not ttl:
            return queryset.count(), True

        key = self._count_key(request)
        cached = cache_utils.cache_get(key)
        if isinstance(cached, int) and cached >= 0:
            return cached, False
        count = queryset.count()
        cache_utils.cache_set(key, count, ttl)
        return count, True

    def _resolve_page_number(self, request, num_pages, count_is_fresh):
        raw = request.query_params.get(self.page_query_param) or 1
        if raw in self.last_page_strings:
            return max(1, num_pages)
        try:
            number = int(raw)
        except (TypeError, ValueError):
            raise NotFound(
                self.invalid_page_message.format(page_number=raw, message="")
            )
        if number < 1:
            raise NotFound(
                self.invalid_page_message.format(page_number=number, message="")
            )
        if number > num_pages:
            if count_is_fresh:
                raise NotFound(
                    self.invalid_page_message.format(page_number=number, message="")
                )
            
        return number

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        count, count_is_fresh = self._served_count(queryset, request)
        paginator = _ServedCountPaginator(page_size, count)
        page_number = self._resolve_page_number(
            request, paginator.num_pages, count_is_fresh
        )

        bottom = (page_number - 1) * page_size
        top = bottom + page_size
        self.page = Page(list(queryset[bottom:top]), page_number, paginator)

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True

        return list(self.page)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


class LargeListPagination(StandardResultsSetPagination):
    page_size = 1000
    max_page_size = 1000
