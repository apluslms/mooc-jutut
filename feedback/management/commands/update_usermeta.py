import time
from django.core.management.base import BaseCommand, CommandError

from aplus_client.client import AplusTokenClient

from ..command_utils import get_courses
from ...models import Student, StudentTag, Feedback

class Command(BaseCommand):
    help = 'Reload submission data from aplus'

    def add_arguments(self, parser):
        parser.add_argument('-s', '--site',
                            help="Domain of aplus site or 'all'")
        parser.add_argument('-c', '--course',
                            help="If there is more than one course, give code of the course you are reloading or 'all'. "
                                 "The code may be either the database id or the course code.",
                            )
        parser.add_argument('-t', '--token',
                            required=True,
                            help="API token for user that has permission to update select users")
        parser.add_argument('--no-students',
                            action='store_true',
                            help="Do not update student data, unless student doesn't exists")
        parser.add_argument('--no-taggings',
                            action='store_true',
                            help="Do not update taggings")
        parser.add_argument('--wait',
                            type=int, default=200,
                            help="How long to wait between updating two feedbacks in milliseconds")

    def handle(self, *args, **options):
        token = options['token']
        wait = options['wait']/1000
        courses = get_courses(self, site_domain=options['site'], course_code=options['course'])

        client = AplusTokenClient(token, debug_enabled=True)

        if not options['no_students']:
            if courses:
                students = Student.objects.get_students_on_courses(courses)
            else:
                students = Student.objects.all()
            for student in students:
                self.stdout.write(self.style.NOTICE(
                    "Working on {}, {}"
                    .format(student, student.url)))
                student.update_using(client)
                student.save()

        if not options['no_taggings']:
            for course in courses:
                self.stdout.write(self.style.NOTICE(
                    "Updating tags for course {}, {}"
                    .format(course, course.url)))
                tag_summary = StudentTag.update_from_api(client, course)
                self.stdout.write(self.style.SUCCESS(
                    "  Tags updated. {} new, {} updated, {} deleted."
                    .format(
                        len(tag_summary['new']),
                        len(tag_summary['updated']),
                        len(tag_summary['deleted']),
                    )))

