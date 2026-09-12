from rest_framework import serializers

from core.models import Announcement, AnnouncementRecipient, Member
from core.status import get_counts


class MemberSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "full_name", "email", "classification", "role", "local_id"]


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    classification = serializers.CharField(source="classification_filter", required=False, allow_blank=True)

    class Meta:
        model = Announcement
        fields = ["title", "body", "needs_ack", "classification"]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("title cannot be blank")
        return value

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("body cannot be blank")
        return value


class AnnouncementSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "local_id",
            "title",
            "body",
            "needs_ack",
            "classification_filter",
            "sent_at",
            "created_at",
            "counts",
        ]

    def get_counts(self, obj):
        return get_counts(obj.id)


class AnnouncementRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementRecipient
        fields = [
            "id",
            "announcement_id",
            "member_id",
            "delivery_status",
            "sent_at",
            "read_at",
            "acknowledged_at",
            "rsvp",
        ]


class DraftRequestSerializer(serializers.Serializer):
    raw_text = serializers.CharField(allow_blank=False, trim_whitespace=True)
