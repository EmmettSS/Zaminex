"""A row hidden from a list must still be reachable by its own id.

Both the reference-data endpoints and the follow-up endpoint narrow their
queryset for the list view — active rows only, non-archived only. Applying that
narrowing to detail routes as well made a row unreachable the moment it was
switched off: the management screen could deactivate a district and then be
unable to delete or restore it, and an archived follow-up could never be
unarchived.

These tests pin the corrected behaviour.
"""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.basics.models import Attribute, City, District, Province
from apps.followups.models import FollowUp

User = get_user_model()


class ReferenceDataDetailRouteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="vis-admin", password="pw", role="ADMIN"
        )
        province = Province.objects.create(name="p1", display_name="استان")
        city = City.objects.create(province=province, name="c1", display_name="شهر")
        cls.district = District.objects.create(
            city=city, name="d1", display_name="محله"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _deactivate(self):
        response = self.client.patch(
            f"/basics/api/districts/{self.district.pk}/",
            {"isActive": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_a_deactivated_row_is_hidden_from_the_list(self):
        self._deactivate()
        listed = self.client.get("/basics/api/districts/").json()
        self.assertNotIn(self.district.pk, [row["id"] for row in listed])

    def test_all_shows_it_again(self):
        self._deactivate()
        listed = self.client.get("/basics/api/districts/?all=1").json()
        self.assertIn(self.district.pk, [row["id"] for row in listed])

    def test_a_deactivated_row_can_still_be_fetched_by_id(self):
        self._deactivate()
        response = self.client.get(f"/basics/api/districts/{self.district.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_a_deactivated_row_can_still_be_deleted(self):
        """The bug: the delete button did nothing once a row was switched off."""
        self._deactivate()
        response = self.client.delete(f"/basics/api/districts/{self.district.pk}/")
        self.assertEqual(response.status_code, 204)

    def test_a_deactivated_row_can_be_reactivated(self):
        self._deactivate()
        response = self.client.patch(
            f"/basics/api/districts/{self.district.pk}/",
            {"isActive": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.district.refresh_from_db()
        self.assertTrue(self.district.is_active)

    def test_the_same_holds_for_attributes(self):
        attribute = Attribute.objects.filter(is_core=False).first()
        self.client.patch(
            f"/basics/api/attributes/{attribute.pk}/",
            {"isActive": False},
            content_type="application/json",
        )

        self.assertEqual(
            self.client.get(f"/basics/api/attributes/{attribute.pk}/").status_code, 200
        )
        self.assertEqual(
            self.client.delete(f"/basics/api/attributes/{attribute.pk}/").status_code,
            204,
        )


class ArchivedFollowUpDetailRouteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="fu-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="fu-agent", password="pw", role="AGENT"
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.followup = FollowUp.objects.create(
            title="پیگیری",
            contact_name="مشتری",
            consultant=self.agent,
        )

    def _archive(self):
        response = self.client.post(
            f"/followupa/api/followups/{self.followup.pk}/archive/"
        )
        self.assertEqual(response.status_code, 200)

    def test_an_archived_followup_is_hidden_from_the_default_list(self):
        self._archive()
        listed = self.client.get("/followupa/api/followups/").json()
        rows = listed["results"] if isinstance(listed, dict) else listed
        self.assertNotIn(self.followup.pk, [row["id"] for row in rows])

    def test_it_appears_in_the_archived_list(self):
        self._archive()
        listed = self.client.get("/followupa/api/followups/?archived=true").json()
        rows = listed["results"] if isinstance(listed, dict) else listed
        self.assertIn(self.followup.pk, [row["id"] for row in rows])

    def test_an_archived_followup_can_still_be_fetched(self):
        self._archive()
        response = self.client.get(f"/followupa/api/followups/{self.followup.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_an_archived_followup_can_be_unarchived(self):
        """Otherwise archiving was a one-way trip."""
        self._archive()
        response = self.client.post(
            f"/followupa/api/followups/{self.followup.pk}/unarchive/"
        )
        self.assertEqual(response.status_code, 200)
        self.followup.refresh_from_db()
        self.assertFalse(self.followup.is_archived)

    def test_an_archived_followup_can_be_deleted(self):
        """The bug: the delete button 404'd on anything archived."""
        self._archive()
        response = self.client.delete(f"/followupa/api/followups/{self.followup.pk}/")
        self.assertEqual(response.status_code, 204)
