import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Local(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class MemberManager(BaseUserManager):
    def create_user(self, email, password, local, **extra_fields):
        if not email:
            raise ValueError("Members must have an email address")
        email = self.normalize_email(email)
        member = self.model(email=email, local=local, **extra_fields)
        member.set_password(password)
        member.save(using=self._db)
        return member


class Member(AbstractBaseUser):
    ROLE_MEMBER = "member"
    ROLE_LEADERSHIP = "leadership"
    ROLE_CHOICES = [(ROLE_MEMBER, "Member"), (ROLE_LEADERSHIP, "Leadership")]

    STATUS_ACTIVE = "active"
    STATUS_RETIRED = "retired"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETIRED, "Retired"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    local = models.ForeignKey(Local, related_name="members", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    classification = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MemberManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    @property
    def is_leadership(self):
        return self.role == self.ROLE_LEADERSHIP

    def __str__(self):
        return f"{self.full_name} ({self.local_id})"


class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    local = models.ForeignKey(Local, related_name="announcements", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    body = models.TextField()
    needs_ack = models.BooleanField(default=False)
    classification_filter = models.CharField(max_length=100, blank=True, null=True)
    request_id = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(
        Member, related_name="announcements_created", on_delete=models.SET_NULL, null=True
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["local", "request_id"],
                name="uq_announcement_local_request",
                condition=models.Q(request_id__isnull=False),
            )
        ]

    def __str__(self):
        return self.title


class AnnouncementRecipient(models.Model):
    DELIVERY_PENDING = "pending"
    DELIVERY_SENT = "sent"
    DELIVERY_FAILED = "failed"
    DELIVERY_UNDELIVERABLE = "undeliverable"
    DELIVERY_CHOICES = [
        (DELIVERY_PENDING, "Pending"),
        (DELIVERY_SENT, "Sent"),
        (DELIVERY_FAILED, "Failed"),
        (DELIVERY_UNDELIVERABLE, "Undeliverable"),
    ]

    RSVP_COMING = "coming"
    RSVP_CANT = "cant"
    RSVP_NO_RESPONSE = "no_response"
    RSVP_CHOICES = [
        (RSVP_COMING, "Coming"),
        (RSVP_CANT, "Cant"),
        (RSVP_NO_RESPONSE, "No response"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(Announcement, related_name="recipients", on_delete=models.CASCADE)
    member = models.ForeignKey(Member, related_name="received_announcements", on_delete=models.CASCADE)

    delivery_status = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default=DELIVERY_PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    rsvp = models.CharField(max_length=20, choices=RSVP_CHOICES, default=RSVP_NO_RESPONSE)
    rsvp_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["announcement", "member"], name="uq_recipient_announcement_member")
        ]
        indexes = [
            models.Index(fields=["announcement", "delivery_status"]),
            models.Index(fields=["announcement", "rsvp"]),
        ]
