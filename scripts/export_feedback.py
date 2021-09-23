"""
Script for exporting a JSON data dump of the feedback.

Usage:
- switch to the jutut user that has access to the database and activate the venv
- move (cd) to the mooc-jutut root directory
- run "python scripts/export_feedback.py ID"
  where ID is the Jutut Course ID.

TODO convert this to a Django manage.py CLI script.
"""

import json


class FeedbackStream(list):

    def __init__(self, course):
        from feedback.models import Feedback
        self.all = Feedback.objects.filter(exercise__course=course)
        self.iterated = 0

    def __iter__(self):
        self.iterated = 0
        for data in self.all.all():
            exercise = data.exercise_id
            student = data.student_id
            feedback = '\n'.join(f[1] for f in data.text_feedback)
            if feedback:
                yield {
                    'exercise': exercise,
                    'student': student,
                    'feedback': feedback,
                    'date': data.timestamp.strftime('%Y-%m-%d'),
                }
                self.iterated += 1

    def __len__(self):
        return self.all.count()


def main(course):
    from feedback.models import Course
    if isinstance(course, int):
        course = Course.objects.get(id=course)
    elif course.isdigit():
        course = Course.objects.get(id=int(course))
    else:
        course = Course.objects.get(html_url__endswith=course.rstrip('/')+'/')
    fn = '/tmp/data_%s_%s.json' % (course.code.lower(), course.instance_name.lower())
    stream = FeedbackStream(course)
    with open(fn, 'w') as out:
        json.dump(stream, out)
    print("Wrote %d entries to %s" % (stream.iterated, fn))


if __name__ == '__main__':
    import os, sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(root)
    os.chdir(root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jutut.settings")

    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application() # load django engine, so models are initialized
    main(int(sys.argv[1]))


# vim: ai et ts=4 sw=4
