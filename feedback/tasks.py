from functools import partial
from datetime import datetime, timezone
from celery import shared_task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger

from .models import (
    Feedback,
    Course,
    StudentTag,
)
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

    newest = feedback.newest_version
    if feedback != newest:
        update_response_to_aplus(newest)

    # on error, retry
    if not ok:
        logger.warning("Task upload_response failed with %d: %s", code, message)
        delay = 5*3**min(self.request.retries, 4) * 60 # :05, :15, :45, 2:15, 6:45
        raise self.retry(countdown=delay)


def async_response_upload(feedback):
    feedback.response_uploaded = 0 # reset upload status

    def send():
        # Signature could be used instead, but this way we can call the
        # returned function and log message at correct time.
        # Signature would require .delay() instead of ().
        t = upload_response.delay(feedback.id)
        logger.debug("Scheduling upload for feedback %d: %s", feedback.id, t.task_id)
    return send


@task(rate_limit="3/m")
def schedule_failed(self): # pylint: disable=unused-argument
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


@task
def update_student_tags(self): # pylint: disable=unused-argument
    # Update the student tags for all courses that have not ended yet
    courses = Course.objects.all()
    # Possible improvement: If Jutut could know which courses are still running
    # (without accessing A+ api), do the next steps only for them
    for course in courses:
        staff = course.staff.all()
        if not staff:
            continue
        # select a random staff member from course to get API token and client
        user = staff[0]
        client = user.get_api_client(course.namespace)
        if not client:
            logger.debug("No client found for %s for the course %s.", user, course)
            continue
        # check if course is still in progress
        course_api = client.load_data(course.url)
        if course_api == None:
            logger.warning("Could not load course data for %s.", course)
            continue
        course_end = datetime.fromisoformat(course_api.get("ending_time"))
        if datetime.now(timezone.utc) < course_end:
            # update tags
            StudentTag.update_from_api(client, course)
