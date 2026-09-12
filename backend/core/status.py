from django.core.cache import cache

from core.models import AnnouncementRecipient

CACHE_KEY_TEMPLATE = "announcement_stats:{id}"


def cache_key(announcement_id) -> str:
    return CACHE_KEY_TEMPLATE.format(id=announcement_id)


def compute_counts(announcement_id) -> dict:
    recipients = AnnouncementRecipient.objects.filter(announcement_id=announcement_id)
    return {
        "total": recipients.count(),
        "sent": recipients.filter(delivery_status="sent").count(),
        "read": recipients.filter(read_at__isnull=False).count(),
        "acknowledged": recipients.filter(acknowledged_at__isnull=False).count(),
        "failed": recipients.filter(delivery_status__in=["failed", "undeliverable"]).count(),
    }


def refresh_cached_counts(announcement_id, ttl_seconds: int | None = None) -> dict:
    from django.conf import settings

    counts = compute_counts(announcement_id)
    cache.set(cache_key(announcement_id), counts, timeout=ttl_seconds or settings.STATUS_CACHE_TTL_SECONDS)
    return counts


def get_counts(announcement_id) -> dict:
    """Cache first, matching the send path design: the worker keeps this
    warm after every batch, and a request only falls back to a live query
    when the cache has expired."""
    cached = cache.get(cache_key(announcement_id))
    if cached is not None:
        return cached
    return refresh_cached_counts(announcement_id)
