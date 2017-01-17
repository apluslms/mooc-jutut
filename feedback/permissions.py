from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.functional import cached_property

from . import (
    SITES_SESSION_KEY,
    COURSES_SESSION_KEY,
)


class ManagePermissionsRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    permission_classes = []

    def get_permissions(self):
        return [Permission() for Permission in self.permission_classes]

    def test_func(self):
        request = self.request
        permissions = self.get_permissions()
        if not permissions:
            raise RuntimeError("View {} doesn't have any permissions defined".format(self.__class__.__name__))
        for permission in permissions:
            if not permission.has_permission(request, self):
                return False
        return True

    @cached_property
    def visible_sites(self):
        return self.request.session.get(SITES_SESSION_KEY, ())

    @cached_property
    def visible_courses(self):
        return self.request.session.get(COURSES_SESSION_KEY, ())



class Permission:
    def has_permission(self, request, view):
        return True


class AdminOrSiteStaffPermission(Permission):
    def has_permission(self, request, view):
        user = request.user
        site_id = view.kwargs.get('site_id')
        if user.is_superuser or user.is_staff or site_id is None:
            return True
        return int(site_id) in view.visible_sites


class AdminOrCourseStaffPermission(Permission):
    def has_permission(self, request, view):
        user = request.user
        course_id = int(view.kwargs.get('course_id', -1))
        return (
            user.is_superuser or
            user.is_staff or
            course_id in view.visible_courses
        )


class AdminOrFeedbackStaffPermission(Permission):
    def has_permission(self, request, view):
        user = request.user
        course_id = view.object.exercise.course.id
        return (
            user.is_superuser or
            user.is_staff or
            course_id in view.visible_courses
        )


class AdminOrTagStaffPermission(Permission):
    def has_permission(self, request, view):
        user = request.user
        feedback, tag = view.tag_objects
        course_id = feedback.exercise.course.id
        return (
            user.is_superuser or
            user.is_staff or
            course_id in view.visible_courses
        )
