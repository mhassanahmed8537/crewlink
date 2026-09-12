import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Announcement, AnnouncementRecipient, Local, Member

CLASSIFICATIONS = [
    "Journeyman Wireman",
    "Apprentice 3rd Year",
    "Apprentice 1st Year",
    "Foreman",
]

LEADERSHIP_PASSWORD = "leadership123"
MEMBER_PASSWORD = "member123"
SEED_ANNOUNCEMENT_REQUEST_ID = "seed-already-sent-announcement"

# A fixed namespace so the handful of ids this exercise's README and
# DESIGN.md quote by value, the two locals, the four named logins, and the
# already sent announcement, come out the same on every fresh
# docker compose up, not just on a re-run against an existing database.
# Bulk filler members are not quoted anywhere and keep random ids.
SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "local27-callout-system")


def seeded_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


class Command(BaseCommand):
    help = (
        "Re-runnable seed: two locals, members across classifications, one "
        "leadership and one member login per local, and one already sent "
        "announcement with recipient rows in the larger local."
    )

    def handle(self, *args, **options):
        random.seed(1337)

        with transaction.atomic():
            local_27 = self._seed_local("Local 27", target_count=2000)
            local_84 = self._seed_local("Local 84", target_count=200)

            leader_27 = self._seed_login(
                local_27,
                email="leader@local27.example",
                password=LEADERSHIP_PASSWORD,
                full_name="Denise Okafor",
                role=Member.ROLE_LEADERSHIP,
                classification="Business Manager",
            )
            self._seed_login(
                local_27,
                email="member@local27.example",
                password=MEMBER_PASSWORD,
                full_name="Alex Rivera",
                role=Member.ROLE_MEMBER,
                classification="Journeyman Wireman",
            )
            self._seed_login(
                local_84,
                email="leader@local84.example",
                password=LEADERSHIP_PASSWORD,
                full_name="Priya Nandy",
                role=Member.ROLE_LEADERSHIP,
                classification="Business Manager",
            )
            member_84 = self._seed_login(
                local_84,
                email="member@local84.example",
                password=MEMBER_PASSWORD,
                full_name="Sam Okoye",
                role=Member.ROLE_MEMBER,
                classification="Apprentice 3rd Year",
            )

            announcement = self._seed_sent_announcement(local_27, leader_27)

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write(f"local_27_id={local_27.id}")
        self.stdout.write(f"local_84_id={local_84.id}")
        self.stdout.write(f"existing_announcement_id={announcement.id}")
        self.stdout.write(f"local_84_member_id={member_84.id}")

    def _seed_local(self, name, target_count):
        local, _ = Local.objects.get_or_create(name=name, defaults={"id": seeded_id(f"local:{name}")})
        existing = local.members.count()
        missing = max(0, target_count - existing)

        batch = []
        for offset in range(missing):
            idx = existing + offset
            classification = CLASSIFICATIONS[idx % len(CLASSIFICATIONS)]
            member = Member(
                local=local,
                full_name=f"Member {idx:05d} of {name}",
                email=f"{name.lower().replace(' ', '')}.member{idx:05d}@example.org",
                classification=classification,
                status=Member.STATUS_ACTIVE,
                role=Member.ROLE_MEMBER,
            )
            member.set_unusable_password()
            batch.append(member)

        if batch:
            Member.objects.bulk_create(batch, batch_size=500, ignore_conflicts=True)

        return local

    def _seed_login(self, local, email, password, full_name, role, classification):
        member = Member.objects.filter(email=email).first()
        if member is None:
            # Built directly, not through create_user, so the id can be set
            # before the first save. A primary key is not something to
            # rewrite after the row already exists.
            member = Member(
                id=seeded_id(f"member:{email}"),
                email=Member.objects.normalize_email(email),
                local=local,
                full_name=full_name,
                classification=classification,
                role=role,
                status=Member.STATUS_ACTIVE,
            )
            member.set_password(password)
            member.save()
        else:
            member.local = local
            member.full_name = full_name
            member.classification = classification
            member.role = role
            member.status = Member.STATUS_ACTIVE
            member.set_password(password)
            member.save()
        return member

    def _seed_sent_announcement(self, local, leader):
        existing = Announcement.objects.filter(local=local, request_id=SEED_ANNOUNCEMENT_REQUEST_ID).first()
        if existing is not None:
            return existing

        sent_at = timezone.now() - timedelta(days=2)
        announcement = Announcement.objects.create(
            id=seeded_id(f"announcement:{SEED_ANNOUNCEMENT_REQUEST_ID}"),
            local=local,
            title="Emergency meeting, Thursday 6pm at the hall",
            body=(
                "Contractor is pulling crews off the westside job. Everyone needs to be "
                "there, this is the third time this has come up."
            ),
            needs_ack=True,
            request_id=SEED_ANNOUNCEMENT_REQUEST_ID,
            created_by=leader,
            sent_at=sent_at,
        )

        member_ids = list(
            Member.objects.filter(local=local, status=Member.STATUS_ACTIVE).values_list("id", flat=True)
        )
        rows = [AnnouncementRecipient(announcement=announcement, member_id=member_id) for member_id in member_ids]
        AnnouncementRecipient.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)

        recipients = list(AnnouncementRecipient.objects.filter(announcement=announcement))
        for recipient in recipients:
            roll = random.random()
            if roll < 0.90:
                recipient.delivery_status = AnnouncementRecipient.DELIVERY_SENT
                recipient.sent_at = sent_at
                if random.random() < 0.65:
                    recipient.read_at = sent_at + timedelta(minutes=random.randint(1, 180))
                    if random.random() < 0.55:
                        recipient.acknowledged_at = recipient.read_at + timedelta(minutes=random.randint(1, 30))
                        recipient.rsvp = random.choice(
                            [AnnouncementRecipient.RSVP_COMING, AnnouncementRecipient.RSVP_CANT]
                        )
                        recipient.rsvp_updated_at = recipient.acknowledged_at
            else:
                recipient.delivery_status = random.choice(
                    [AnnouncementRecipient.DELIVERY_FAILED, AnnouncementRecipient.DELIVERY_UNDELIVERABLE]
                )

        AnnouncementRecipient.objects.bulk_update(
            recipients,
            ["delivery_status", "sent_at", "read_at", "acknowledged_at", "rsvp", "rsvp_updated_at"],
            batch_size=500,
        )

        return announcement
