from rest_framework.permissions import BasePermission

from core.models import Member


class IsLocalLeadership(BasePermission):
    """
    Rule 1, the leadership half: only an authenticated member whose role is
    leadership may reach the view this is attached to.
    """

    message = "This action is restricted to leadership."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", None) == Member.ROLE_LEADERSHIP


class LocalScopedQuerysetMixin:
    """
    Rule 1, the local boundary half: every queryset this mixin touches is
    filtered to the caller's own local_id before anything else runs. A new
    endpoint is only unsafe if it skips this mixin and queries the model
    directly, which is a visible choice in a diff, not a forgotten line
    inside a view.
    """

    local_field = "local_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return queryset.none()
        filter_kwargs = {self.local_field: user.local_id}
        return queryset.filter(**filter_kwargs)


class LeadershipScopedViewSet(LocalScopedQuerysetMixin):
    """
    Combines the local boundary with the leadership permission check, for
    endpoints leadership uses to manage their own local's data.
    """

    permission_classes = [IsLocalLeadership]
