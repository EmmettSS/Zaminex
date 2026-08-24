import datetime
import json
import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.tasks.models import Task

from .models import (
    Ticket,
    TicketAttachment,
    TicketAuditAction,
    TicketMessage,
    TicketParticipantRole,
)


User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="zaminex-ticket-tests-"))
class TicketSecurityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ticket_admin",
            password="pass12345",
            first_name="مدیر",
            role=UserRole.ADMIN,
        )
        self.owner = User.objects.create_user(
            username="ticket_owner",
            password="pass12345",
            first_name="ثبت کننده",
            role=UserRole.AGENT,
        )
        self.recipient = User.objects.create_user(
            username="ticket_recipient",
            password="pass12345",
            first_name="گیرنده",
            role=UserRole.AGENT,
        )
        self.other_recipient = User.objects.create_user(
            username="ticket_other_recipient",
            password="pass12345",
            first_name="گیرنده دوم",
            role=UserRole.AGENT,
        )
        self.stranger = User.objects.create_user(
            username="ticket_stranger",
            password="pass12345",
            first_name="غریبه",
            role=UserRole.AGENT,
        )
        self.task = Task.objects.create(
            title="وظیفه قابل دسترسی",
            assigned_to=self.owner,
            created_by=self.owner,
            due_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        self.other_task = Task.objects.create(
            title="وظیفه خصوصی کارشناس دیگر",
            assigned_to=self.recipient,
            created_by=self.recipient,
            due_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _create_ticket(self, recipients=None, subject_id=None):
        self._auth(self.owner)
        return self.client.post(
            "/tickets/api/tickets/",
            {
                "ticketType": "REQUEST",
                "priority": "IMPORTANT",
                "subjectType": "TASK",
                "subjectId": subject_id or self.task.id,
                "recipientIds": recipients or [self.recipient.id],
                "message": "لطفاً این وظیفه را بررسی کنید.",
            },
            format="json",
        )

    def _multipart_ticket_payload(self, **overrides):
        """Mirror the browser FormData payload (including JSON array strings)."""

        payload = {
            "ticketType": "REQUEST",
            "priority": "NORMAL",
            "subjectType": "TASK",
            "subjectId": str(self.task.id),
            "recipientIds": json.dumps([self.recipient.id]),
            "message": "لطفاً این وظیفه را بررسی کنید.",
        }
        payload.update(overrides)
        return payload

    def test_multipart_create_accepts_browser_json_recipient_ids_and_string_subject_id(self):
        self._auth(self.owner)
        response = self.client.post(
            "/tickets/api/tickets/",
            self._multipart_ticket_payload(),
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        ticket = Ticket.objects.get(pk=response.json()["id"])
        self.assertEqual(ticket.subject_id, self.task.id)
        self.assertEqual(ticket.messages.count(), 1)
        self.assertEqual(
            ticket.participants.filter(role=TicketParticipantRole.RECIPIENT).count(), 1
        )
        self.assertTrue(
            ticket.participants.filter(
                role=TicketParticipantRole.RECIPIENT, user=self.recipient
            ).exists()
        )

    def test_multipart_create_accepts_multiple_json_recipients_without_nesting(self):
        self._auth(self.owner)
        recipient_ids = [self.recipient.id, self.other_recipient.id]
        response = self.client.post(
            "/tickets/api/tickets/",
            self._multipart_ticket_payload(recipientIds=json.dumps(recipient_ids)),
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        ticket = Ticket.objects.get(pk=response.json()["id"])
        self.assertSetEqual(
            set(
                ticket.participants.filter(
                    role=TicketParticipantRole.RECIPIENT
                ).values_list("user_id", flat=True)
            ),
            set(recipient_ids),
        )

    def test_multipart_create_accepts_repeated_recipient_fields(self):
        self._auth(self.owner)
        recipient_ids = [self.recipient.id, self.other_recipient.id]
        response = self.client.post(
            "/tickets/api/tickets/",
            self._multipart_ticket_payload(
                recipientIds=[str(recipient_id) for recipient_id in recipient_ids]
            ),
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(
            Ticket.objects.get(pk=response.json()["id"])
            .participants.filter(role=TicketParticipantRole.RECIPIENT)
            .count(),
            len(recipient_ids),
        )

    def test_multipart_create_accepts_json_tags(self):
        self._auth(self.owner)
        tags = ["فوری", "بررسی"]
        response = self.client.post(
            "/tickets/api/tickets/",
            self._multipart_ticket_payload(tags=json.dumps(tags)),
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(Ticket.objects.get(pk=response.json()["id"]).tags, tags)

    def test_json_create_accepts_native_recipient_and_tag_lists(self):
        self._auth(self.owner)
        tags = ["فوری", "بررسی"]
        response = self.client.post(
            "/tickets/api/tickets/",
            {
                "ticketType": "REQUEST",
                "priority": "NORMAL",
                "subjectType": "TASK",
                "subjectId": self.task.id,
                "recipientIds": [self.recipient.id, self.other_recipient.id],
                "message": "ثبت تیکت از JSON.",
                "tags": tags,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        ticket = Ticket.objects.get(pk=response.json()["id"])
        self.assertEqual(ticket.tags, tags)
        self.assertEqual(
            ticket.participants.filter(role=TicketParticipantRole.RECIPIENT).count(), 2
        )

    def test_multipart_validation_errors_remain_field_specific(self):
        self._auth(self.owner)
        response = self.client.post(
            "/tickets/api/tickets/",
            {"ticketType": "REQUEST", "subjectType": "TASK", "message": "ناقص"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("subject_id", response.json())
        self.assertIn("recipient_ids", response.json())

    def test_agent_cannot_create_ticket_about_another_agents_task(self):
        response = self._create_ticket(subject_id=self.other_task.id)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_sender_and_recipients_are_scoped_and_initial_ticket_is_unread(self):
        response = self._create_ticket()
        self.assertEqual(response.status_code, 201, response.content)
        ticket = Ticket.objects.get()
        self.assertTrue(ticket.ticket_number.startswith("TKT-"))
        self.assertEqual(ticket.reply_count, 0)
        self.assertEqual(ticket.participants.count(), 2)

        self._auth(self.owner)
        sent = self.client.get("/tickets/api/tickets/?folder=sent")
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.json()["count"], 1)
        self.assertFalse(sent.json()["results"][0]["isUnread"])

        self._auth(self.recipient)
        received = self.client.get("/tickets/api/tickets/?folder=received")
        self.assertEqual(received.status_code, 200)
        row = received.json()["results"][0]
        self.assertTrue(row["isUnread"])
        self.assertEqual(row["waitingForLabel"], "در انتظار پاسخ من")

        detail = self.client.get(f"/tickets/api/tickets/{ticket.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["isRead"])
        self.assertEqual(len(detail.json()["messages"]), 1)

        received_after_read = self.client.get("/tickets/api/tickets/?folder=received")
        self.assertFalse(received_after_read.json()["results"][0]["isUnread"])

    def test_replies_are_visible_to_owner_and_addressed_recipient_only(self):
        response = self._create_ticket(
            recipients=[self.recipient.id, self.other_recipient.id]
        )
        ticket_id = response.json()["id"]

        self._auth(self.recipient)
        reply = self.client.post(
            f"/tickets/api/tickets/{ticket_id}/reply/",
            {"message": "پاسخ خصوصی کارشناس اول"},
            format="json",
        )
        self.assertEqual(reply.status_code, 200, reply.content)
        self.assertEqual(len(reply.json()["messages"]), 2)

        self._auth(self.other_recipient)
        other_view = self.client.get(f"/tickets/api/tickets/{ticket_id}/")
        self.assertEqual(other_view.status_code, 200)
        self.assertEqual(len(other_view.json()["messages"]), 1)
        self.assertEqual(other_view.json()["messages"][0]["isInitial"], True)
        self.assertEqual(other_view.json()["replyCount"], 0)
        self.assertEqual(other_view.json()["hasReply"], False)
        self.assertEqual(len(other_view.json()["recipients"]), 1)

        self._auth(self.owner)
        owner_view = self.client.get(f"/tickets/api/tickets/{ticket_id}/")
        self.assertEqual(owner_view.status_code, 200)
        self.assertEqual(len(owner_view.json()["messages"]), 2)
        self.assertEqual(Ticket.objects.get(pk=ticket_id).reply_count, 1)

    def test_unrelated_consultant_cannot_see_ticket_or_attachment(self):
        response = self._create_ticket()
        ticket_id = response.json()["id"]
        self._auth(self.stranger)
        detail = self.client.get(f"/tickets/api/tickets/{ticket_id}/")
        self.assertEqual(detail.status_code, 404)
        listing = self.client.get("/tickets/api/tickets/?folder=received")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 0)

    def test_recipient_can_close_and_owner_can_reopen(self):
        response = self._create_ticket()
        ticket_id = response.json()["id"]
        self._auth(self.recipient)
        closed = self.client.post(f"/tickets/api/tickets/{ticket_id}/close/")
        self.assertEqual(closed.status_code, 200, closed.content)
        self.assertEqual(closed.json()["status"], "CLOSED")

        self._auth(self.owner)
        reopened = self.client.post(f"/tickets/api/tickets/{ticket_id}/reopen/")
        self.assertEqual(reopened.status_code, 200, reopened.content)
        self.assertEqual(reopened.json()["status"], "WAITING_REPLY")

        actions = list(
            Ticket.objects.get(pk=ticket_id).audit_events.values_list(
                "action", flat=True
            )
        )
        self.assertIn(TicketAuditAction.CLOSED, actions)
        self.assertIn(TicketAuditAction.REOPENED, actions)

    def test_admin_can_monitor_all_and_export(self):
        response = self._create_ticket()
        ticket_id = response.json()["id"]
        self._auth(self.admin)
        all_tickets = self.client.get("/tickets/api/tickets/?folder=all")
        self.assertEqual(all_tickets.status_code, 200)
        self.assertEqual(all_tickets.json()["count"], 1)
        detail = self.client.get(f"/tickets/api/tickets/{ticket_id}/")
        self.assertEqual(detail.status_code, 200)
        export = self.client.get("/tickets/api/tickets/export/?folder=all")
        self.assertEqual(export.status_code, 200)
        self.assertIn("TKT-", export.content.decode("utf-8-sig"))

    def test_safe_pdf_attachments_are_stored_and_returned_only_to_participants(self):
        self._auth(self.owner)
        response = self.client.post(
            "/tickets/api/tickets/",
            self._multipart_ticket_payload(
                ticketType="ISSUE",
                attachments=[
                    SimpleUploadedFile(
                        "evidence.pdf",
                        b"%PDF-1.7\nbody",
                        content_type="application/pdf",
                    ),
                    SimpleUploadedFile(
                        "second-evidence.pdf",
                        b"%PDF-1.7\nsecond body",
                        content_type="application/pdf",
                    ),
                ],
            ),
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())
        attachments = response.json()["messages"][0]["attachments"]
        self.assertEqual(len(attachments), 2)
        attachment_id = attachments[0]["id"]
        self.assertTrue(TicketAttachment.objects.filter(pk=attachment_id).exists())

        self._auth(self.recipient)
        download = self.client.get(
            f"/tickets/api/attachments/{attachment_id}/download/"
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/octet-stream")
        payload = b"".join(download.streaming_content)
        self.assertEqual(payload[:5], b"%PDF-")

        self._auth(self.stranger)
        forbidden_download = self.client.get(
            f"/tickets/api/attachments/{attachment_id}/download/"
        )
        self.assertEqual(forbidden_download.status_code, 404)

    def test_rejects_fake_attachment_extension_and_rolls_back_everything(self):
        self._auth(self.owner)
        response = self.client.post(
            "/tickets/api/tickets/",
            self._multipart_ticket_payload(
                message="فایل نامعتبر.",
                attachments=SimpleUploadedFile(
                    "fake.pdf", b"not a pdf", content_type="application/pdf"
                ),
            ),
            format="multipart",
        )
        self.assertEqual(response.status_code, 400, response.json())
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(TicketMessage.objects.count(), 0)
        self.assertEqual(TicketAttachment.objects.count(), 0)

    def test_reply_accepts_multipart_text_and_attachment(self):
        created = self._create_ticket()
        self.assertEqual(created.status_code, 201, created.json())
        ticket_id = created.json()["id"]
        self._auth(self.recipient)

        text_reply = self.client.post(
            f"/tickets/api/tickets/{ticket_id}/reply/",
            {"message": "پاسخ متنی multipart"},
            format="multipart",
        )
        self.assertEqual(text_reply.status_code, 200, text_reply.json())
        self.assertEqual(TicketMessage.objects.filter(ticket_id=ticket_id).count(), 2)
        self.assertEqual(
            TicketMessage.objects.get(ticket_id=ticket_id, is_initial=False).body,
            "پاسخ متنی multipart",
        )

        attachment_reply = self.client.post(
            f"/tickets/api/tickets/{ticket_id}/reply/",
            {
                "message": "پاسخ همراه فایل",
                "attachments": SimpleUploadedFile(
                    "reply.pdf",
                    b"%PDF-1.7\nreply",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(attachment_reply.status_code, 200, attachment_reply.json())
        reply_message = TicketMessage.objects.filter(
            ticket_id=ticket_id, is_initial=False
        ).order_by("-id").first()
        self.assertEqual(reply_message.body, "پاسخ همراه فایل")
        self.assertEqual(reply_message.attachments.count(), 1)
        self.assertEqual(reply_message.attachments.first().original_name, "reply.pdf")
