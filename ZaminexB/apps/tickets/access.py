"""Object-level access rules for ticket subjects and conversations.

These functions are deliberately shared by the create serializer, subject
lookups, list queryset and attachment download endpoint.  Keeping the rules in
one module prevents a UI-only permission check from becoming a data leak.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q

from apps.common.access import can_access_property, user_is_admin
from apps.followups.models import FollowUp
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

from .models import Ticket, TicketParticipant, TicketParticipantRole, TicketSubject


User = get_user_model()


SUBJECT_FIELD_NAMES = {
    TicketSubject.PROPERTY: "property",
    TicketSubject.LISTING: "listing",
    TicketSubject.FOLLOWUP: "followup",
    TicketSubject.TASK: "task",
    TicketSubject.TICKET: "related_ticket",
}


def is_active_recipient(user) -> bool:
    if not user or not getattr(user, "is_active", False):
        return False
    if getattr(user, "role", "") == "AGENT":
        profile = getattr(user, "consultant_profile", None)
        return bool(profile is None or profile.is_active)
    if getattr(user, "role", "") == "ADMIN":
        profile = getattr(user, "admin_profile", None)
        return bool(profile is None or profile.is_active)
    return False


def active_recipient_queryset(current_user=None):
    """All valid human recipients, excluding the current account."""

    qs = User.objects.filter(is_active=True, role__in=["ADMIN", "AGENT"])
    if current_user and getattr(current_user, "is_authenticated", False):
        qs = qs.exclude(pk=current_user.pk)
    # Keep inactive profiles out of the picker as well as out of validation.
    # The NULL branches preserve compatibility with older data that has a
    # user row but no profile yet (for example a freshly-created admin).
    qs = qs.filter(
        (
            Q(role="AGENT")
            & (
                Q(consultant_profile__isnull=True)
                | Q(consultant_profile__is_active=True)
            )
        )
        | (
            Q(role="ADMIN")
            & (Q(admin_profile__isnull=True) | Q(admin_profile__is_active=True))
        )
    )
    return qs.select_related("consultant_profile", "admin_profile").order_by(
        "first_name", "last_name", "username"
    )


def can_view_ticket(user, ticket: Ticket) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user_is_admin(user):
        return True
    if ticket.created_by_id == user.pk:
        return True
    return ticket.participants.filter(
        user_id=user.pk, role=TicketParticipantRole.RECIPIENT
    ).exists()


def visible_ticket_queryset(user):
    """Base queryset for a user, with all list/detail relations prefetched."""

    if not user or not getattr(user, "is_authenticated", False):
        return Ticket.objects.none()

    qs = Ticket.objects.select_related(
        "created_by",
        "last_message_sender",
        "property",
        "listing",
        "listing__property",
        "followup",
        "followup__consultant",
        "task",
        "task__assigned_to",
        "task__created_by",
        "related_ticket",
        "related_ticket__created_by",
        "closed_by",
    )
    qs = qs.prefetch_related(
        Prefetch(
            "participants",
            queryset=TicketParticipant.objects.select_related(
                "user", "last_visible_sender"
            ).order_by("role", "user__first_name", "user__last_name", "user__username"),
            to_attr="_ticket_participants",
        )
    )

    if user_is_admin(user):
        return qs.all().distinct()

    return qs.filter(
        Q(created_by_id=user.pk)
        | Q(
            participants__user_id=user.pk,
            participants__role=TicketParticipantRole.RECIPIENT,
        )
    ).distinct()


def subject_queryset_for_user(user, subject_type: str):
    """Return only records the user may use as a ticket subject."""

    if subject_type == TicketSubject.PROPERTY:
        qs = Property.objects.select_related("consultant", "district")
        if not user_is_admin(user):
            qs = qs.filter(Q(consultant_id=user.pk) | Q(is_shared=True))
        return qs

    if subject_type == TicketSubject.LISTING:
        qs = Listing.objects.select_related("property", "created_by", "assigned_to")
        if not user_is_admin(user):
            qs = qs.filter(Q(created_by_id=user.pk) | Q(assigned_to_id=user.pk))
        return qs

    if subject_type == TicketSubject.FOLLOWUP:
        qs = FollowUp.objects.select_related("consultant", "property")
        if not user_is_admin(user):
            qs = qs.filter(consultant_id=user.pk)
        return qs

    if subject_type == TicketSubject.TASK:
        qs = Task.objects.select_related("assigned_to", "created_by", "property")
        if not user_is_admin(user):
            qs = qs.filter(Q(assigned_to_id=user.pk) | Q(created_by_id=user.pk))
        return qs

    if subject_type == TicketSubject.TICKET:
        return visible_ticket_queryset(user)

    return Property.objects.none()


def get_subject_for_user(user, subject_type: str, subject_id):
    """Resolve and authorize a concrete subject, or return ``None``."""

    if subject_type not in SUBJECT_FIELD_NAMES:
        return None
    try:
        return subject_queryset_for_user(user, subject_type).get(pk=subject_id)
    except (
        Property.DoesNotExist,
        Listing.DoesNotExist,
        FollowUp.DoesNotExist,
        Task.DoesNotExist,
        Ticket.DoesNotExist,
    ):
        return None


def subject_is_accessible(user, subject_type: str, subject) -> bool:
    """Check an already-loaded object without trusting its serialized id."""

    if subject is None:
        return False
    if user_is_admin(user):
        return True

    if subject_type == TicketSubject.PROPERTY:
        return can_access_property(user, subject)
    if subject_type == TicketSubject.LISTING:
        return subject.created_by_id == user.pk or subject.assigned_to_id == user.pk
    if subject_type == TicketSubject.FOLLOWUP:
        return subject.consultant_id == user.pk
    if subject_type == TicketSubject.TASK:
        return subject.assigned_to_id == user.pk or subject.created_by_id == user.pk
    if subject_type == TicketSubject.TICKET:
        return can_view_ticket(user, subject)
    return False


def participant_for_user(ticket: Ticket, user):
    """Use the prefetch cache when present; otherwise perform one safe query."""

    cached = getattr(ticket, "_ticket_participants", None)
    if cached is not None:
        for participant in cached:
            if participant.user_id == user.pk:
                return participant
        return None
    return (
        ticket.participants.select_related("user", "last_visible_sender")
        .filter(user_id=user.pk)
        .first()
    )


def message_is_visible_to_user(message, user, ticket: Ticket) -> bool:
    """Private reply visibility rule used by the detail endpoint."""

    if user_is_admin(user):
        return True
    if ticket.created_by_id == user.pk:
        return True
    if message.thread_recipient_id is None:
        return True
    return message.thread_recipient_id == user.pk


def participant_can_reply(ticket: Ticket, user) -> bool:
    if user_is_admin(user):
        return True
    return (
        ticket.created_by_id == user.pk
        or ticket.participants.filter(
            user_id=user.pk, role=TicketParticipantRole.RECIPIENT
        ).exists()
    )


def participant_recipient_ids(ticket: Ticket) -> list[int]:
    return list(
        ticket.participants.filter(role=TicketParticipantRole.RECIPIENT).values_list(
            "user_id", flat=True
        )
    )
