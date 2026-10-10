from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import admin_required
from apps.common.fuzzy_search import apply_fuzzy_search
from apps.common.pagination import StandardResultsSetPagination
from apps.properties.models import Property
from .models import Listing
from .serializers import ListingListSerializer, ListingSerializer


def _sync_property_status_from_listings(listing):
    property_id = getattr(listing, "property_id", None)
    if not property_id:
        return

    with transaction.atomic():
        prop = (
            Property.objects.select_for_update().filter(pk=property_id).first()
        )
        if prop is None:
            return

        other_sold = Listing.objects.filter(
            property_id=property_id,
            status=Listing.Status.SOLD,
        ).exclude(pk=listing.pk).exists()

        if listing.status == Listing.Status.SOLD:
            new_status = Property.Status.SOLD
        elif other_sold:
            new_status = Property.Status.SOLD
        else:
            new_status = Property.Status.AVAILABLE

        if prop.status != new_status:
            prop.status = new_status
            prop.save(update_fields=["status", "updated_at"])


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ListingListSerializer
        return ListingSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "list":
            from apps.analytics.metrics import annotate_effective_prices

            property_ids = set(
                self.filter_queryset(self.get_queryset())
                .values_list("property_id", flat=True)
            )
            context["effective_price_map"] = annotate_effective_prices(property_ids)
        return context

    def get_queryset(self):
        user = self.request.user
        if user.role == "ADMIN":
            qs = Listing.objects.all().select_related(
                'property', 'created_by', 'assigned_to', 'deal_type'
            )
        else:
            qs = Listing.objects.filter(
                Q(created_by=user) | Q(assigned_to=user)
            ).select_related('property', 'created_by', 'assigned_to', 'deal_type')

        if self.action == "list":
            qs = qs.select_related(
                'assigned_to__consultant_profile',
                'created_by__consultant_profile',
            ).prefetch_related(
                'property__images',
                'property__followups',
                'property__tasks',
            )
        else:
            qs = qs.prefetch_related('property__images')

        if getattr(self, "action", None) != "list":
            return qs.order_by("-created_at")

        q = self.request.query_params.get("q")
        fuzzy_search_active = bool(q and q.strip())
        if q:
            qs = apply_fuzzy_search(
                qs,
                q,
                [
                    "title",
                    "description",
                    "id",
                    "property__title",
                    "property__internal_code",
                    "property__address",
                    "property__neighborhood",
                    "property__district__display_name",
                    "property__district__name",
                    "assigned_to__consultant_profile__full_name",
                    "assigned_to__username",
                    "assigned_to__first_name",
                    "assigned_to__last_name",
                ],
            )

        status_param = self.request.query_params.get("status")
        show_sold = self.request.query_params.get("show_sold") or self.request.query_params.get("showSold")
        include_sold = self.request.query_params.get("include_sold") or self.request.query_params.get("includeSold")

        if status_param:
            qs = qs.filter(status__iexact=status_param)
        elif str(show_sold).lower() in ("true", "1"):
            qs = qs.filter(status=Listing.Status.SOLD)
        elif str(include_sold).lower() in ("true", "1"):
            pass
        else:
            qs = qs.exclude(status=Listing.Status.SOLD)

        consultant = self.request.query_params.get("consultant") or self.request.query_params.get("assigned_to")
        if consultant and user.role == "ADMIN":
            if str(consultant).isdigit():
                qs = qs.filter(assigned_to_id=consultant)
            else:
                qs = apply_fuzzy_search(qs, consultant, ["assigned_to__username"])

        prop = self.request.query_params.get("property")
        if prop:
            if str(prop).isdigit():
                qs = qs.filter(property_id=prop)
            else:
                qs = apply_fuzzy_search(qs, prop, ["property__title"])

        deal_type = self.request.query_params.get("dealType") or self.request.query_params.get("deal_type")
        if deal_type:
            if str(deal_type).isdigit():
                qs = qs.filter(deal_type_id=deal_type)
            else:
                qs = apply_fuzzy_search(
                    qs, deal_type, ["deal_type__display_name", "deal_type__name"]
                )

        rent_min = self.request.query_params.get("rentMin")
        rent_max = self.request.query_params.get("rentMax")
        if rent_min:
            qs = qs.filter(monthly_rent__gte=rent_min)
        if rent_max:
            qs = qs.filter(monthly_rent__lte=rent_max)

        deposit_min = self.request.query_params.get("depositMin")
        deposit_max = self.request.query_params.get("depositMax")
        if deposit_min:
            qs = qs.filter(deposit__gte=deposit_min)
        if deposit_max:
            qs = qs.filter(deposit__lte=deposit_max)

        sale_min = self.request.query_params.get("saleMin")
        sale_max = self.request.query_params.get("saleMax")
        if sale_min or sale_max:
            if sale_min and sale_max:
                qs = qs.filter(
                    Q(sale_price__gte=sale_min, sale_price__lte=sale_max) |
                    Q(deposit__gte=sale_min, deposit__lte=sale_max)
                )
            elif sale_min:
                qs = qs.filter(
                    Q(sale_price__gte=sale_min) |
                    Q(deposit__gte=sale_min)
                )
            elif sale_max:
                qs = qs.filter(
                    Q(sale_price__lte=sale_max) |
                    Q(deposit__lte=sale_max)
                )

        if fuzzy_search_active:
            return qs
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if request.user.role != "ADMIN":
            return Response({"detail": "فقط مدیران می‌توانند آگهی‌ها را تأیید کنند."}, status=status.HTTP_403_FORBIDDEN)
        listing = self.get_object()
        listing.status = Listing.Status.ACTIVE
        listing.save(update_fields=['status', 'updated_at'])
        return Response(ListingSerializer(listing).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if request.user.role != "ADMIN":
            return Response({"detail": "فقط مدیران می‌توانند آگهی‌ها را رد کنند."}, status=status.HTTP_403_FORBIDDEN)
        listing = self.get_object()
        listing.status = Listing.Status.DRAFT
        listing.save(update_fields=['status', 'updated_at'])
        return Response(ListingSerializer(listing).data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        listing = self.get_object()
        if request.user.role != "ADMIN" and listing.created_by != request.user:
            return Response({"detail": "شما اجازه انجام این عملیات را ندارید."}, status=status.HTTP_403_FORBIDDEN)
            
        if listing.status == Listing.Status.ACTIVE:
            listing.status = Listing.Status.PAUSED
        elif listing.status == Listing.Status.PAUSED:
            listing.status = Listing.Status.ACTIVE
        else:
            return Response({"detail": "آگهی باید فعال یا متوقف‌شده باشد."}, status=status.HTTP_400_BAD_REQUEST)
            
        listing.save(update_fields=['status', 'updated_at'])
        return Response(ListingSerializer(listing).data)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        listing = self.get_object()
        if request.user.role != "ADMIN" and listing.created_by != request.user:
            return Response({"detail": "شما اجازه انجام این عملیات را ندارید."}, status=status.HTTP_403_FORBIDDEN)
        listing.status = Listing.Status.ARCHIVED
        listing.save(update_fields=['status', 'updated_at'])
        return Response(ListingSerializer(listing).data)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        listing = self.get_object()
        if request.user.role != "ADMIN" and listing.created_by != request.user:
            return Response({"detail": "شما اجازه انجام این عملیات را ندارید."}, status=status.HTTP_403_FORBIDDEN)
        if listing.status != Listing.Status.ARCHIVED:
            return Response({"detail": "آگهی باید بایگانی‌شده باشد."}, status=status.HTTP_400_BAD_REQUEST)
        listing.status = Listing.Status.ACTIVE
        listing.save(update_fields=['status', 'updated_at'])
        return Response(ListingSerializer(listing).data)

    @action(detail=True, methods=['post'])
    def sold(self, request, pk=None):
        listing = self.get_object()
        if request.user.role != "ADMIN" and listing.created_by != request.user and listing.assigned_to != request.user:
            return Response({"detail": "شما اجازه انجام این عملیات را ندارید."}, status=status.HTTP_403_FORBIDDEN)
        listing.status = Listing.Status.SOLD
        listing.save(update_fields=['status', 'updated_at'])
        _sync_property_status_from_listings(listing)
        return Response(ListingSerializer(listing).data)

    @action(detail=True, methods=['post'])
    def set_status(self, request, pk=None):
        listing = self.get_object()
        user = request.user
        if user.role != "ADMIN" and listing.created_by != user and listing.assigned_to != user:
            return Response({"detail": "شما اجازه انجام این عملیات را ندارید."}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status") or request.query_params.get("status")
        valid_statuses = [choice.value for choice in Listing.Status]
        if not new_status or str(new_status) not in valid_statuses:
            return Response({"detail": "وضعیت نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

        listing.status = str(new_status)
        listing.save(update_fields=['status', 'updated_at'])
        _sync_property_status_from_listings(listing)

        return Response(ListingSerializer(listing).data)


@login_required
def listing_list(request):
    return render(request, "listings/listing_list.html", {"listing_props": {}})
