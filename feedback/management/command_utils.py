from django.core.management.base import CommandError

from ..models import (
    Site,
    Course,
    Feedback,
)


def get_feedback_queryset(self,
                          feedback_id=None,
                          site_domain=None,
                          course_code=None):
    feedbacks = Feedback.objects.select_related('exercise', 'exercise__course', 'exercise__course__namespace').all()
    feedbacks_c = 0
    sites = None
    courses = None

    if feedback_id is not None:
        feedbacks = feedbacks.filter(id=feedback_id)
        feedbacks_c = feedbacks.count()
        if feedbacks_c == 0:
            raise CommandError("Feedback with id {} doesn't exist.".format(feedback_id))
        return feedbacks, feedbacks_c

    sites = Site.objects.all().all()
    if site_domain == 'all':
        if course_code == 'all':
            feedbacks_c = feedbacks.count()
            if feedbacks_c == 0:
                raise CommandError("No feedbacks in the system,")
            self.stdout.write(self.style.SUCCESS("Fount a total of {} feedbacks".format(feedbacks_c)))
            return feedbacks, feedbacks_c
        elif sites.count() == 0:
            raise CommandError("No sites in the system.")
    elif site_domain:
        sites = sites.filter(domain=site_domain)
        if sites.count() == 0:
            raise CommandError("No sites found with domain '{}'".format(site_domain))
    else:
        self.stdout.write(self.style.NOTICE("List of possible site domains:"))
        for site in Site.objects.all():
            self.stdout.write(self.style.SUCCESS("  {}".format(site.domain)))
        raise CommandError("No site domain or feedback id given")

    courses = Course.objects.select_related('namespace').all()
    if site_domain != 'all':
        courses = courses.filter(namespace__in=sites)
    if course_code and course_code != 'all':
        courses = courses.filter(code=course_code)
    courses_c = courses.count()
    if courses_c == 0:
        raise CommandError("No courses found")

    self.stdout.write(self.style.NOTICE("Selected courses:"))
    courses_out = ["{}: {} - {}".format(course.namespace.domain, course.code, course.name) for course in courses]
    for course in sorted(courses_out):
        self.stdout.write(self.style.SUCCESS("  {}".format(course)))

    if not course_code and courses_c != 1:
        raise CommandError("More than one course found. Use flag -c to lomit")

    feedbacks = feedbacks.filter(exercise__course__in=courses)
    feedbacks_c = feedbacks.count()
    self.stdout.write(self.style.SUCCESS("Fount a total of {} feedbacks".format(feedbacks_c)))

    return feedbacks, feedbacks_c
