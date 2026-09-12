import logging
import random

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.models import Announcement, AnnouncementRecipient, Member
from core.status import refresh_cached_counts

logger = logging.getLogger(__name__)

# Matches the 5 to 10 percent silent push failure rate the exercise is
# designed for. Real push credentials are not required for this exercise,
# so dispatch is simulated at this rate instead of calling a real provider.
SIMULATED_FAILURE_RATE = 0.07
SIMULATED_RETRY_RECOVERY_RATE = 0.7


@shared_task
def dispatch_announcement(announcement_id):
    """
    Runs outside the request/response cycle. Fetches the target audience,
    fans out one recipient row per member in batches, dispatches each
    batch, and refreshes the cached status counts after every batch so the
    status screen never has to run a fresh aggregate query itself.
    """
    try:
        announcement = Announcement.objects.get(id=announcement_id)
    except Announcement.DoesNotExist:
        logger.warning("dispatch_announcement: announcement %s no longer exists", announcement_id)
        return

    members_qs = Member.objects.filter(local_id=announcement.local_id, status=Member.STATUS_ACTIVE)
    if announcement.classification_filter:
        members_qs = members_qs.filter(classification=announcement.classification_filter)

    member_ids = list(members_qs.values_list("id", flat=True))
    batch_size = settings.RECIPIENT_BATCH_SIZE

    for start in range(0, len(member_ids), batch_size):
        batch_ids = member_ids[start : start + batch_size]

        # The insert that makes Rule 2 true: a retried or restarted batch
        # lands on the same (announcement, member) rows and does nothing
        # for any that already exist, no matter which worker handles it.
        rows = [
            AnnouncementRecipient(announcement_id=announcement.id, member_id=member_id)
            for member_id in batch_ids
        ]
        AnnouncementRecipient.objects.bulk_create(rows, ignore_conflicts=True)

        _dispatch_batch(announcement.id, batch_ids)
        refresh_cached_counts(announcement.id)

    logger.info(
        "dispatch_announcement: announcement=%s local=%s recipients=%d complete",
        announcement.id,
        announcement.local_id,
        len(member_ids),
    )

    # One retry, a few seconds later, for whatever came back failed. Not a
    # second delivery system, just the honest line between a real fix and
    # scope creep, described in DESIGN.md under what I cut.
    retry_failed_deliveries.apply_async(args=[str(announcement.id)], countdown=5)


def _dispatch_batch(announcement_id, member_ids):
    now = timezone.now()
    sent_ids, failed_ids = [], []

    for member_id in member_ids:
        if random.random() < SIMULATED_FAILURE_RATE:
            failed_ids.append(member_id)
        else:
            sent_ids.append(member_id)

    if sent_ids:
        AnnouncementRecipient.objects.filter(
            announcement_id=announcement_id, member_id__in=sent_ids
        ).update(delivery_status=AnnouncementRecipient.DELIVERY_SENT, sent_at=now)
        logger.info("dispatch batch: announcement=%s sent=%d", announcement_id, len(sent_ids))

    if failed_ids:
        AnnouncementRecipient.objects.filter(
            announcement_id=announcement_id, member_id__in=failed_ids
        ).update(delivery_status=AnnouncementRecipient.DELIVERY_FAILED)
        logger.info("dispatch batch: announcement=%s failed=%d", announcement_id, len(failed_ids))


@shared_task
def retry_failed_deliveries(announcement_id):
    """
    The one sweep described in DESIGN.md: anything still failed after the
    first pass gets one more attempt, then is left as a final,
    undeliverable, visible failure rather than retried forever.
    """
    failed = list(
        AnnouncementRecipient.objects.filter(
            announcement_id=announcement_id,
            delivery_status=AnnouncementRecipient.DELIVERY_FAILED,
            retry_count=0,
        )
    )
    if not failed:
        return

    now = timezone.now()
    recovered_ids, still_failed_ids = [], []
    for recipient in failed:
        if random.random() < SIMULATED_RETRY_RECOVERY_RATE:
            recovered_ids.append(recipient.id)
        else:
            still_failed_ids.append(recipient.id)

    if recovered_ids:
        AnnouncementRecipient.objects.filter(id__in=recovered_ids).update(
            delivery_status=AnnouncementRecipient.DELIVERY_SENT, sent_at=now, retry_count=1
        )
    if still_failed_ids:
        AnnouncementRecipient.objects.filter(id__in=still_failed_ids).update(
            delivery_status=AnnouncementRecipient.DELIVERY_UNDELIVERABLE, retry_count=1
        )

    refresh_cached_counts(announcement_id)
    logger.info(
        "retry_failed_deliveries: announcement=%s recovered=%d still_failed=%d",
        announcement_id,
        len(recovered_ids),
        len(still_failed_ids),
    )
