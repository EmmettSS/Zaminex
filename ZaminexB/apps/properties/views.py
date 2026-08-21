from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.basics.models import Attribute
from apps.common.attribute_filters import apply_attribute_filters
from apps.common.fuzzy_search import apply_fuzzy_search
from apps.common.metrics import annotate_effective_prices, effective_sale_price as _sale_price

from .permissions import consultant_required
from .models import Property, PropertyImage

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.access import can_manage_property
from .validators import validate_property_image

from .serializers import PropertySerializer, PropertyImageSerializer
from apps.common.pagination import StandardResultsSetPagination


class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        django_role = getattr(user, "role", "")

        # Everything the serializer touches is loaded up front, otherwise each
        # row costs a handful of extra queries:
        #   listings__deal_type      → the derived `price`
        #   property_type_ref/usage  → the reference-data labels
        #   district chain           → `locationPath`
        #   attribute_values         → the dynamic attributes
        qs = (
            Property.objects.select_related(
                "consultant",
                "property_type_ref",
                "property_usage",
                "district",
                "district__city",
                "district__city__province",
            )
            .prefetch_related(
                "images",
                "followups",
                "tasks",
                "listings__deal_type",
                "attribute_values__attribute",
            )
        )

        if django_role != "ADMIN":
            qs = qs.filter(Q(consultant=user) | Q(is_shared=True))

        search_query = self.request.query_params.get("q")
        # Free-text search over title, internal code and address. The actual
        # matching and relevance ranking is delegated to TrigramSimilarity search
        # through the shared helper; when active, its score ordering is preserved below.
        fuzzy_search_active = bool(search_query and search_query.strip())
        if search_query:
            qs = apply_fuzzy_search(
                qs,
                search_query,
                [
                    "title",
                    "internal_code",
                    "address",
                    "neighborhood",
                    "description",
                    "district__display_name",
                    "district__name",
                    "district__city__display_name",
                    "district__city__province__display_name",
                    "consultant__consultant_profile__full_name",
                    "consultant__username",
                    "consultant__first_name",
                    "consultant__last_name",
                ],
            )

        property_type = self.request.query_params.get("type")
        if property_type:
            qs = qs.filter(property_type__iexact=property_type)

        transaction_type = self.request.query_params.get("transactionType")
        if transaction_type:
            if transaction_type.lower() == "sale":
                qs = qs.filter(deal_type=Property.DealType.SALE)
            elif transaction_type.lower() == "rent":
                qs = qs.filter(deal_type=Property.DealType.RENT)

        # -- location filters (province -> city -> district) ------------------
        # City filter: exact match on display name or id, for the new city combobox.
        # The frontend city combobox submits an exact display name, so we match it
        # with plain exact lookups instead of trigram fuzzy search. This avoids a
        # runtime dependency on the optional pg_trgm extension (which was causing a
        # 500 when the city/district filter was used on a database without it).
        city = self.request.query_params.get("city")
        if city:
            if str(city).isdigit():
                qs = qs.filter(district__city_id=city)
            else:
                qs = qs.filter(
                    Q(district__city__display_name__iexact=city)
                    | Q(district__city__name__iexact=city)
                )

        district = self.request.query_params.get("district")
        if district:
            if str(district).isdigit():
                qs = qs.filter(district_id=district)
            else:
                # Legacy text filter on the free-text neighborhood plus the new
                # hierarchical district name. ID input still stays exact.
                qs = qs.filter(
                    Q(neighborhood__iexact=district)
                    | Q(district__display_name__iexact=district)
                    | Q(district__name__iexact=district)
                )

        property_status = self.request.query_params.get("propertyStatus")
        if property_status:
            qs = qs.filter(status__iexact=property_status.upper())

        # Price lives on the listing now, so the range filters resolve through
        # the property's sale listings and fall back to the legacy column for
        # records created before the split — matching what the API reports as
        # `price`, so a filter can never contradict the number on screen.
        price_min = self.request.query_params.get("priceMin")
        price_max = self.request.query_params.get("priceMax")
        if price_min or price_max:
            qs = self._filter_by_price(qs, price_min, price_max)

        consultant_id = self.request.query_params.get("consultantId")
        if consultant_id and django_role == "ADMIN":
            qs = qs.filter(consultant_id=consultant_id)

        # Filters generated from the property type's search attributes, sent as
        # `attr_<name>` / `attr_<name>_min` / `attr_<name>_max`.
        qs = apply_attribute_filters(
            qs,
            self.request.query_params,
            entity=Attribute.Entity.PROPERTY,
            values_relation="attribute_values",
        )

        # Restrict to one property type when the dynamic filter bar is scoped.
        property_type_ref = self.request.query_params.get("propertyTypeRef")
        if property_type_ref:
            if str(property_type_ref).isdigit():
                qs = qs.filter(property_type_ref_id=property_type_ref)
            else:
                qs = qs.filter(property_type_ref__name=property_type_ref)

        # When a free-text search is active, `apply_fuzzy_search` has already
        # ordered the queryset by descending relevance; keep that ordering so
        # pagination surfaces the best matches first. Otherwise fall back to
        # the usual newest-first ordering.
        if fuzzy_search_active:
            return qs
        return qs.order_by("-created_at")

    @staticmethod
    def _filter_by_price(queryset, price_min, price_max):
        """Keep properties whose effective sale price sits in the range.

        The figure is derived, not stored, so the comparison is done in Python
        over the resolved map. The id list is small because every other filter
        has already been applied by this point.
        """
        prices = annotate_effective_prices(list(queryset.values_list("id", flat=True)))

        keep = []
        for row in queryset.values("id", "price"):
            price = prices.get(row["id"], row["price"])
            if price is None:
                continue
            if price_min and price < Decimal(str(price_min)):
                continue
            if price_max and price > Decimal(str(price_max)):
                continue
            keep.append(row["id"])

        return queryset.filter(id__in=keep)

    def perform_create(self, serializer):
        user = self.request.user
        django_role = getattr(user, "role", "")

        if django_role == "ADMIN":
            consultant = serializer.validated_data.get("consultant") or user
        else:
            consultant = user

        serializer.save(consultant=consultant)

    def perform_update(self, serializer):
        user = self.request.user
        django_role = getattr(user, "role", "")
        new_status = serializer.validated_data.get("status")
        if (
            new_status == Property.Status.INACTIVE
            and not can_manage_property(user, serializer.instance)
        ):
            raise PermissionDenied("فقط مالک ملک یا مدیر می‌تواند آن را بایگانی کند.")

        if django_role == "ADMIN":
            consultant = serializer.validated_data.get("consultant", serializer.instance.consultant)
            serializer.save(consultant=consultant)
        else:
            # Consultants keep the original consultant on shared properties.
            if serializer.instance.is_shared:
                serializer.save()
            else:
                serializer.save(consultant=user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_manage_property(request.user, instance):
            return Response(
                {"detail": "فقط مالک ملک یا مدیر می‌تواند آن را حذف کند."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="toggle-shared")
    def toggle_shared(self, request, pk=None):
        """Toggle the is_shared flag. Admin-only."""
        if getattr(request.user, "role", "") != "ADMIN":
            return Response({"detail": "فقط مدیران می‌توانند این تنظیم را تغییر دهند."}, status=403)
        prop = self.get_object()
        prop.is_shared = not prop.is_shared
        prop.save(update_fields=["is_shared"])
        return Response(PropertySerializer(prop, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="images")
    def upload_images(self, request, pk=None):
        property_obj = self.get_object()
        if not can_manage_property(request.user, property_obj):
            return Response(
                {"detail": "فقط مالک ملک یا مدیر می‌تواند تصویر اضافه کند."},
                status=status.HTTP_403_FORBIDDEN,
            )
        files = request.FILES.getlist("images")
        if not files:
            return Response(
                {"detail": "هیچ فایلی ارسال نشده است."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(files) > 10:
            return Response(
                {"detail": "حداکثر ۱۰ تصویر در هر درخواست مجاز است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_images = []
        for f in files:
            try:
                validate_property_image(f)
            except Exception as exc:
                detail = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            img = PropertyImage.objects.create(property=property_obj, image=f)
            created_images.append(PropertyImageSerializer(img, context={'request': request}).data)

        return Response(created_images, status=201)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        property_obj = self.get_object()
        if not can_manage_property(request.user, property_obj):
            return Response(
                {"detail": "فقط مالک ملک یا مدیر می‌تواند تصویر را حذف کند."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            image = PropertyImage.objects.get(pk=image_id, property=property_obj)
        except PropertyImage.DoesNotExist:
            return Response(
                {"detail": "تصویر مورد نظر یافت نشد."},
                status=404,
            )
        image.image.delete(save=False)
        image.delete()
        return Response(status=204)

    @action(detail=True, methods=["patch"], url_path="images-reorder")
    def reorder_images(self, request, pk=None):
        property_obj = self.get_object()
        if not can_manage_property(request.user, property_obj):
            return Response(
                {"detail": "فقط مالک ملک یا مدیر می‌تواند ترتیب تصاویر را تغییر دهد."},
                status=status.HTTP_403_FORBIDDEN,
            )
        order_data = request.data if isinstance(request.data, list) else request.data.get("order", [])
        if not isinstance(order_data, list):
            return Response(
                {"detail": "فرمت ورودی نامعتبر است. لیستی از {id, sort_order} انتظار می‌رود."},
                status=400,
            )
        for item in order_data:
            img_id = item.get("id")
            sort_order = item.get("sort_order")
            if img_id is None or sort_order is None:
                continue
            PropertyImage.objects.filter(
                pk=img_id, property=property_obj
            ).update(sort_order=sort_order)
        images = PropertyImage.objects.filter(
            property=property_obj
        ).order_by("sort_order", "id")
        return Response(
            PropertyImageSerializer(images, many=True, context={"request": request}).data
        )



@login_required
@consultant_required
def property_archive(request, pk):

    property_obj = get_object_or_404(
        Property,
        pk=pk,
        consultant=request.user
    )

    property_obj.status = Property.Status.INACTIVE
    property_obj.save()

    return redirect("properties:property-list")


@ensure_csrf_cookie
@login_required
def property_list(request):
    user = request.user
    django_role = getattr(user, "role", "")
    frontend_role = "admin" if django_role == "ADMIN" else "consultant"

    if frontend_role == "admin":
        properties_qs = Property.objects.all()
    else:
        from django.db.models import Q
        properties_qs = Property.objects.filter(Q(consultant=user) | Q(is_shared=True))

    search_query = request.GET.get("q")
    # Free-text search over title, internal code and address, delegated to the
    # shared search helper so the server-rendered list matches the REST API.
    fuzzy_search_active = bool(search_query and search_query.strip())
    if search_query:
        properties_qs = apply_fuzzy_search(
            properties_qs,
            search_query,
            [
                "title",
                "internal_code",
                "address",
                "neighborhood",
                "description",
                "district__display_name",
                "district__name",
                "district__city__display_name",
                "district__city__province__display_name",
                "consultant__consultant_profile__full_name",
                "consultant__username",
                "consultant__first_name",
                "consultant__last_name",
            ],
        )

    properties_qs = properties_qs.prefetch_related("listings__deal_type")
    # Keep the relevance ordering from `apply_fuzzy_search` when searching so
    # the first page shows the strongest matches; otherwise newest-first.
    if fuzzy_search_active:
        paginator = Paginator(properties_qs, 12)
    else:
        paginator = Paginator(properties_qs.order_by("-created_at"), 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    properties_list = []
    for p in page_obj.object_list:
        is_archived = (p.status == Property.Status.INACTIVE)
        
        properties_list.append({
            "id": str(p.id),
            "internalCode": p.internal_code or "",
            "title": p.title or "",
            "type": (p.property_type or "apartment").lower(),
            "transactionType": "sale" if p.deal_type == "SALE" else "rent",
            "floor": p.floor or 0,
            "constructionYear": p.built_year or 0,
            "fullAddress": p.address or "",
            "propertyStatus": (p.status or "active").lower(),
            "archived": is_archived,
            "price": float(_sale_price(p) or 0),
            "area": p.area or 0,
            "beds": p.rooms or 0,
            "district": p.neighborhood or "",
            "consultant": (p.consultant.get_full_name() or p.consultant.username) if p.consultant else "نامشخص",
            "consultantId": str(p.consultant.id) if p.consultant else "",
            "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
            "views": 0,
            "listed": not is_archived,
            "roi": 0,
            "gradient": "from-emerald-500 to-teal-600"
        })

    initial_data = {
        "isAuthenticated": True,
        "role": frontend_role,
        "userName": user.get_full_name() or user.username,
        "currentConsultantId": str(user.id),
        "initialPage": "properties" if frontend_role == "admin" else "my-properties",
        "loginUrl": "/accounts/login/",
        "logoutUrl": "/accounts/logout/",
        "csrfToken": get_token(request),
        "pageProps": {
            "properties": properties_list,
            "items": properties_list,
            "pagination": {
                "currentPage": page_obj.number,
                "totalPages": paginator.num_pages,
                "totalItems": paginator.count,
                "hasNext": page_obj.has_next(),
                "hasPrevious": page_obj.has_previous()
            }
        }
    }

    return render(request, "dashboard.html", {"initial_data": initial_data})



@login_required
@consultant_required
def property_image_manage(request, pk):
    property_obj = get_object_or_404(
        Property,
        pk=pk,
        consultant=request.user,
    )

    if request.method == "POST":
        formset = PropertyImageFormSet(
            request.POST,
            request.FILES,
            instance=property_obj,
        )
        if formset.is_valid():
            formset.save()
            return redirect("properties:property-update", pk=property_obj.pk)
    else:
        formset = PropertyImageFormSet(instance=property_obj)

    return render(
        request,
        "properties/property_image_form.html",
        {
            "property": property_obj,
            "formset": formset,
        },
    )



def get_common_initial_data(request, page_name):
    user = request.user
    django_role = getattr(user, "role", "")
    return {
        "isAuthenticated": True,
        "role": "admin" if django_role == "ADMIN" else "consultant",
        "userName": user.get_full_name() or user.username,
        "currentConsultantId": str(user.id),
        "initialPage": page_name,
        "csrfToken": get_token(request),
        "pageProps": {}
    }

@ensure_csrf_cookie
@login_required
def property_create_view(request):
    data = get_common_initial_data(request, "add-property")
    
    # Districts are deliberately not embedded here.  The React form obtains the
    # current active list from /common/api/districts/, so changes made in the
    # district-management page are reflected without a frontend deployment.
    return render(request, "dashboard.html", {"initial_data": data})

@ensure_csrf_cookie
@login_required
def property_edit_view(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)
    
    if request.user.role != "ADMIN" and property_obj.consultant != request.user and not property_obj.is_shared:
        return redirect("dashboard")

    data = get_common_initial_data(request, "edit-property")
    
    data["pageProps"] = {
        "propertyData": {
            "id": str(property_obj.id),
            "title": property_obj.title,
            "price": float(_sale_price(property_obj) or 0),
            "area": property_obj.area,
            "rooms": property_obj.rooms,
            "description": property_obj.description,
        }
    }
    
    return render(request, "dashboard.html", {"initial_data": data})

@ensure_csrf_cookie
@login_required
def property_detail(request, pk):
    user = request.user
    django_role = getattr(user, "role", "")
    frontend_role = "admin" if django_role == "ADMIN" else "consultant"

    if frontend_role == "admin":
        property_obj = get_object_or_404(
            Property.objects.prefetch_related("images"),
            pk=pk
        )
    else:
        from django.db.models import Q
        property_obj = get_object_or_404(
            Property.objects.prefetch_related("images"),
            Q(pk=pk),
            Q(consultant=user) | Q(is_shared=True),
        )

    property_data = {
        "id": str(property_obj.id),
        "internalCode": property_obj.internal_code or "",
        "title": property_obj.title or "",
        "type": (property_obj.property_type or "").lower(),
        "transactionType": "sale" if property_obj.deal_type == "SALE" else "rent",
        "floor": property_obj.floor or 0,
        "constructionYear": property_obj.built_year or 0,
        "fullAddress": property_obj.address or "",
        "propertyStatus": (property_obj.status or "").lower(),
        "archived": property_obj.status == Property.Status.INACTIVE,
        "price": float(_sale_price(property_obj) or 0),
        "area": property_obj.area or 0,
        "beds": property_obj.rooms or 0,
        "district": property_obj.neighborhood or "",
        "consultant": (
            (property_obj.consultant.get_full_name() or property_obj.consultant.username)
            if property_obj.consultant else ""
        ),
        "consultantId": str(property_obj.consultant.id) if property_obj.consultant else "",
        "date": property_obj.created_at.strftime("%Y-%m-%d") if property_obj.created_at else "",
        "views": 0,
        "listed": property_obj.status != Property.Status.INACTIVE,
        "roi": 0,
        "gradient": "from-emerald-500 to-teal-600",

        "description": property_obj.description or "",
        "images": [
            {
                "id": str(image.id),
                "url": image.image.url,
                "alt": property_obj.title or "property-image"
            }
            for image in property_obj.images.all()
        ],
    }

    initial_data = {
        "isAuthenticated": True,
        "role": frontend_role,
        "userName": user.get_full_name() or user.username,
        "currentConsultantId": str(user.id),
        "initialPage": "property-detail",
        "loginUrl": "/accounts/login/",
        "logoutUrl": "/accounts/logout/",
        "csrfToken": get_token(request),
        "next": "",
        "pageProps": {
            "property": property_data,
        }
    }

    return render(request, "dashboard.html", {"initial_data": initial_data})
