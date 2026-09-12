from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ai import AIProviderUnavailable, generate_draft
from core.models import Announcement, AnnouncementRecipient
from core.permissions import LeadershipScopedViewSet
from core.serializers import (
    AnnouncementCreateSerializer,
    AnnouncementRecipientSerializer,
    AnnouncementSerializer,
    DraftRequestSerializer,
)
from core.status import refresh_cached_counts
from core.tasks import dispatch_announcement


class LoginView(APIView):
    """POST {email, password} -> {token, member}. No prior auth required."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email", "")
        password = request.data.get("password", "")
        user = authenticate(request, email=email, password=password)
        if user is None or not user.is_active:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "member": {
                    "id": str(user.id),
                    "full_name": user.full_name,
                    "email": user.email,
                    "role": user.role,
                    "local_id": str(user.local_id),
                    "local_name": user.local.name,
                },
            }
        )


class AnnouncementViewSet(LeadershipScopedViewSet, viewsets.ModelViewSet):
    """
    Leadership only, scoped to the caller's own local by
    LeadershipScopedViewSet. Create doubles as send: this exercise's build
    does not need a separate draft-then-send step for manually typed
    announcements, only for AI generated ones, and that approval happens
    client side before this endpoint is ever called.
    """

    queryset = Announcement.objects.all().order_by("-created_at")
    serializer_class = AnnouncementSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def create(self, request, *args, **kwargs):
        request_id = request.headers.get("Idempotency-Key") or request.data.get("request_id") or None
        local_id = request.user.local_id

        if request_id:
            existing = Announcement.objects.filter(local_id=local_id, request_id=request_id).first()
            if existing:
                return Response(AnnouncementSerializer(existing).data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                announcement = serializer.save(
                    local_id=local_id,
                    created_by=request.user,
                    request_id=request_id,
                    sent_at=timezone.now(),
                )
        except IntegrityError:
            # Lost a race to another request carrying the same
            # Idempotency-Key. That request's row is the real one.
            existing = None
            if request_id:
                existing = Announcement.objects.filter(local_id=local_id, request_id=request_id).first()
            if existing:
                return Response(AnnouncementSerializer(existing).data, status=status.HTTP_200_OK)
            raise

        dispatch_announcement.delay(str(announcement.id))
        return Response(AnnouncementSerializer(announcement).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def draft(self, request):
        """
        AI assisted drafting. Never writes anything to the database and
        never sends anything: it only returns text for leadership to
        review, edit, and then submit through the normal create call
        above. If the provider is slow or down, this returns available:
        false rather than an error, so the screen can fall back to a
        blank, manually written draft instead of failing.
        """
        serializer = DraftRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            draft = generate_draft(serializer.validated_data["raw_text"])
        except AIProviderUnavailable as exc:
            return Response({"available": False, "reason": str(exc)}, status=status.HTTP_200_OK)
        return Response({"available": True, **draft}, status=status.HTTP_200_OK)


class AnnouncementReadView(APIView):
    """A member marks their own recipient row read. Nothing else."""

    def post(self, request, pk):
        recipient = get_object_or_404(AnnouncementRecipient, announcement_id=pk, member=request.user)
        if recipient.read_at is None:
            recipient.read_at = timezone.now()
            recipient.save(update_fields=["read_at"])
            refresh_cached_counts(pk)
        return Response(AnnouncementRecipientSerializer(recipient).data)


class AnnouncementAcknowledgeView(APIView):
    """A member marks their own recipient row acknowledged, and read if it wasn't already."""

    def post(self, request, pk):
        recipient = get_object_or_404(AnnouncementRecipient, announcement_id=pk, member=request.user)
        now = timezone.now()
        update_fields = []
        if recipient.read_at is None:
            recipient.read_at = now
            update_fields.append("read_at")
        if recipient.acknowledged_at is None:
            recipient.acknowledged_at = now
            update_fields.append("acknowledged_at")
        if update_fields:
            recipient.save(update_fields=update_fields)
            refresh_cached_counts(pk)
        return Response(AnnouncementRecipientSerializer(recipient).data)
