from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views import (
    AnnouncementAcknowledgeView,
    AnnouncementReadView,
    AnnouncementViewSet,
    LoginView,
)

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("announcements/<uuid:pk>/read/", AnnouncementReadView.as_view(), name="announcement-read"),
    path(
        "announcements/<uuid:pk>/acknowledge/",
        AnnouncementAcknowledgeView.as_view(),
        name="announcement-acknowledge",
    ),
] + router.urls
