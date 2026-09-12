import pytest
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Announcement, AnnouncementRecipient, Local, Member
from core.tasks import dispatch_announcement

pytestmark = pytest.mark.django_db


@pytest.fixture
def local_a():
    return Local.objects.create(name="Local A")


@pytest.fixture
def leader_a(local_a):
    return Member.objects.create_user(
        email="leader@a.example",
        password="pw-12345",
        local=local_a,
        full_name="Leader A",
        classification="Business Manager",
        role=Member.ROLE_LEADERSHIP,
    )


@pytest.fixture
def members_a(local_a):
    members = []
    for i in range(25):
        member = Member(
            local=local_a,
            full_name=f"Member {i}",
            email=f"member{i}@a.example",
            classification="Journeyman Wireman",
            role=Member.ROLE_MEMBER,
        )
        member.set_unusable_password()
        members.append(member)
    Member.objects.bulk_create(members)
    return list(Member.objects.filter(local=local_a, role=Member.ROLE_MEMBER))


class TestRule2Idempotency:
    """
    Verifies Rule 2 under the two ways it can actually be broken: leadership
    retrying a send that looked stuck, and a worker restarting mid job.
    """

    def test_retried_create_request_is_not_a_second_send(self, leader_a, members_a):
        client = APIClient()
        client.force_authenticate(user=leader_a)
        headers = {"HTTP_IDEMPOTENCY_KEY": "retry-key-1"}

        first = client.post(
            "/api/v1/announcements/", {"title": "Retry test", "body": "body"}, format="json", **headers
        )
        second = client.post(
            "/api/v1/announcements/", {"title": "Retry test", "body": "body"}, format="json", **headers
        )

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_200_OK
        assert first.data["id"] == second.data["id"]
        assert Announcement.objects.filter(local=leader_a.local, request_id="retry-key-1").count() == 1

        # Every active member of the local receives it, leadership included,
        # since leadership is itself a member. Not doubled by the retry.
        expected_recipients = Member.objects.filter(local=leader_a.local, status=Member.STATUS_ACTIVE).count()
        recipient_count = AnnouncementRecipient.objects.filter(announcement_id=first.data["id"]).count()
        assert recipient_count == expected_recipients

    def test_restarted_worker_does_not_double_insert_recipients(self, leader_a, members_a):
        announcement = Announcement.objects.create(
            local=leader_a.local, title="Crash test", body="body", created_by=leader_a
        )

        dispatch_announcement(str(announcement.id))
        dispatch_announcement(str(announcement.id))  # a second worker picking up the same job

        expected_recipients = Member.objects.filter(local=leader_a.local, status=Member.STATUS_ACTIVE).count()
        member_ids = list(
            AnnouncementRecipient.objects.filter(announcement=announcement).values_list("member_id", flat=True)
        )
        assert len(member_ids) == expected_recipients
        assert len(set(member_ids)) == len(member_ids)
