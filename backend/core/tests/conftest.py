import pytest


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    """
    Run Celery tasks synchronously, in process, during tests, so a test can
    call the create endpoint and immediately assert on the recipient rows
    the dispatch task produced, without a real broker or worker.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
