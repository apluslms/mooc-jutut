import json
import os.path
import tempfile

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from feedback.models import Course, Feedback, Student


class FeedbackStream(list):

    def __init__(self, course):
        self.all = Feedback.objects.filter(exercise__course=course)
        self.iterated = 0

    def __iter__(self):
        self.iterated = 0
        for data in self.all.all():
            feedback = '\n'.join(f[1] for f in data.text_feedback)
            if feedback:
                yield {
                    'exercise': data.exercise_id,
                    'uid': data.student_id,
                    'feedback': feedback,
                    'date': str(data.timestamp),
                }
                self.iterated += 1

    def __len__(self):
        return self.all.count()


class StudentStream(list):

    def __init__(self, course):
        self.all = Student.objects.get_students_on_course(course)
        self.iterated = 0

    def __iter__(self):
        self.iterated = 0
        for data in self.all.all():
            yield {
                'uid': data.id,
                'student': data.student_id,
                'tags': list(map(lambda t: str(t), data.tags.all())),
            }
            self.iterated += 1

    def __len__(self):
        return self.all.count()


class Command(BaseCommand):
    help = "Export feedback and student data from a course into a JSON dump."

    def add_arguments(self, parser):
        parser.add_argument(
            'course_id',
            type=int,
            nargs='?',
            default=None,
            help="Jutut Course ID",
        )
        parser.add_argument(
            '-s',
            '--course-slug',
            help="Jutut Course URL key. This is used to select the course if no 'course_id' parameter is given.",
        )
        parser.add_argument(
            '-f',
            '--feedback-file',
            help="File path to the output feedback JSON file.",
        )
        parser.add_argument(
            '-u',
            '--student-file',
            help="File path to the output student JSON file.",
        )

    def handle(self, *args, **options):
        try:
            if options['course_id'] is not None:
                course_id = options['course_id']
                course = Course.objects.get(id=course_id)
            elif options['course_slug']:
                course_id = options['course_slug']
                course = Course.objects.get(html_url__endswith=course_id.rstrip('/') + '/')
            else:
                raise CommandError("Either 'course_id' or '--course-slug' parameter must be given!")
        except Course.DoesNotExist:
            raise CommandError(f'Course "{course_id}" does not exist.')

        now = timezone.now()
        fb_fn = (options['feedback_file'] or
            os.path.join(
                tempfile.gettempdir(),
                'jutut_feedback_data_%s_%s_%s.json' % (
                    course.code.lower(), course.instance_name.lower(), now.strftime('%Y-%m-%dT%H-%M')
                )
            )
        )
        fb_stream = FeedbackStream(course)
        with open(fb_fn, 'w') as out:
            json.dump(fb_stream, out)

        student_fn = (options['student_file'] or
            os.path.join(
                tempfile.gettempdir(),
                'jutut_student_data_%s_%s_%s.json' % (
                    course.code.lower(), course.instance_name.lower(), now.strftime('%Y-%m-%dT%H-%M')
                )
            )
        )
        student_stream = StudentStream(course)
        with open(student_fn, 'w') as out:
            json.dump(student_stream, out)

        self.stdout.write(
            f"Wrote {fb_stream.iterated} feedback entries to {fb_fn} and\n"
            f"{student_stream.iterated} student entries to {student_fn}",
        )

# vim: ai et ts=4 sw=4
