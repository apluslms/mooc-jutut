import time
from django.core.management.base import BaseCommand, CommandError

from ..command_utils import get_feedback_queryset
from ...utils import update_response_to_aplus

class Command(BaseCommand):
    help = 'Reload submission data from aplus'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--feedback',
                            type=int, default=None,
                            help="Reload single feedback (use id)")
        parser.add_argument('-s', '--site',
                            help="Domain of aplus site or 'all'")
        parser.add_argument('-c', '--course',
                            help="If there is more than one course, give code of the course you are reloading or 'all'")
        parser.add_argument('--max-retries',
                            type=int, default=20,
                            help="Do not retry if there has been this many retries before. set 0 to ignore")
        parser.add_argument('--wait',
                            type=int, default=200,
                            help="How long to wait between uploading two feedbacks in milliseconds")

    def handle(self, *args, **options):
        wait = options['wait']/1000

        feedbacks, feedbacks_count = get_feedback_queryset(
            self,
            options['feedback'],
            options['site'],
            options['course'],
        )

        feedbacks = feedbacks.filter_flags(feedbacks.FILTER_FLAGS.UPL_ERROR)
        if feedbacks_count > 0 and options['max_retries'] > 0:
            feedbacks = feedbacks.filter(_response_upl_attempt__lte=options['max_retries'])

        feedbacks = feedbacks.order_by('_response_upl_at').select_related(None)

        feedbacks_count = feedbacks.count()
        if feedbacks_count == 0:
            self.stdout.write(self.style.SUCCESS("No feedbacks to update"))
            return
        self.stdout.write(self.style.SUCCESS("Going to reupload {} failed feedbacks.".format(feedbacks_count)))

        for feedback in feedbacks:
            self.stdout.write(self.style.NOTICE("Retrying {} to '{}' having old status {}".format(feedback.id, feedback.submission_url, feedback.response_uploaded)))

            if feedback.response_uploaded.ok:
                feedback.response_notify = response.NOTIFY.NO

            update_response_to_aplus(feedback)
            feedback.save(update_fields=[])

            status = feedback.response_uploaded
            if status.ok:
                self.stdout.write(self.style.SUCCESS("  Upload ok"))
            else:
                self.stdout.write(self.style.ERROR("  Upload failed with {}".format(status)))


            # sleep for some time, so we don't flood api service
            time.sleep(wait)
