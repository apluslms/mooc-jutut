from functools import partial
from celery import shared_task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger

from .models import Feedback
from .utils import update_response_to_aplus


logger = get_task_logger(__name__)
task = partial(shared_task, bind=True, ignore_result=True)


@task(max_retries=15, rate_limit='1/s')
def upload_response(self, feedback_id):
    # get feedback
    feedback = Feedback.objects.get(id=feedback_id)

    # if for some reason feedback is uploaded ok, ignore it
    if feedback.response_uploaded.ok:
        raise Ignore()

    # make upload
    ok, code, message = update_response_to_aplus(feedback)
    feedback.save(update_fields=[])

    # on error, retry
    if not ok:
        logger.warning("Task upload_response failed with %d: %s", code, message)
        delay = 5*3**min(self.request.retries, 4) * 60 # :05, :15, :45, 2:15, 6:45
        raise self.retry(countdown=delay)


@task(rate_limit="3/m")
def schedule_failed(self):
    # this will get feedbacks that are
    #  - have error and
    #  a) upload is not tried in an hour of set
    #  b) upload has failed and last trie is 9 hours ago
    feedbacks = Feedback.objects.filter_missed_upload(time_gap_min=60)
    if not feedbacks.exists():
        feedbacks = Feedback.objects.filter_failed_upload(max_tries=50, time_gap_min=9*60)

    for feedback in feedbacks[:100]:
        t = upload_response.delay(feedback.id)
        logger.debug("Scheduling upload for feedback %d: %s", feedback.id, t.task_id)
