import pytest
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Announcement, Local, Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def local_a():
    return Local.objects.create(name="Local A")


@pytest.fixture
def local_b():
    return Local.objects.create(name="Local B")


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
def member_b(local_b):
    return Member.objects.create_user(
        email="member@b.example",
        password="pw-12345",
        local=local_b,
        full_name="Member B",
        classification="Apprentice 1st Year",
        role=Member.ROLE_MEMBER,
    )


@pytest.fixture
def announcement_a(local_a, leader_a):
    return Announcement.objects.create(local=local_a, title="Local A only", body="body", needs_ack=True, created_by=leader_a)


class TestRule1Boundaries:
    """
    Verifies the boundary a leadership account in one local cannot cross
    (into another local's data) and the boundary a member account cannot
    cross (into a leadership only action), the two halves of Rule 1.
    """

    def test_leader_list_excludes_other_locals_announcements(self, leader_a, announcement_a, local_b):
        other = Announcement.objects.create(local=local_b, title="Local B only", body="body")

        client = APIClient()
        client.force_authenticate(user=leader_a)
        response = client.get("/api/v1/announcements/")

        assert response.status_code == status.HTTP_200_OK
        ids = {row["id"] for row in response.data["results"]}
        assert str(announcement_a.id) in ids
        assert str(other.id) not in ids

    def test_leader_cannot_retrieve_other_locals_announcement(self, leader_a, local_b):
        other = Announcement.objects.create(local=local_b, title="Local B only", body="body")

        client = APIClient()
        client.force_authenticate(user=leader_a)
        response = client.get(f"/api/v1/announcements/{other.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_member_cannot_create_announcement(self, member_b):
        client = APIClient()
        client.force_authenticate(user=member_b)
        response = client.post("/api/v1/announcements/", {"title": "x", "body": "y"}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_member_cannot_read_announcement_outside_their_local(self, member_b, announcement_a):
        client = APIClient()
        client.force_authenticate(user=member_b)
        response = client.post(f"/api/v1/announcements/{announcement_a.id}/read/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
