from django.contrib import admin
from django_colortag.admin import ColorTagAdmin

from .models import (
    Student,
    Course,
    Exercise,
    Feedback,
    FeedbackTag,
    ContextTag,
)


@admin.register(Course, Exercise, Feedback, Student)
class CachedAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None): # pylint: disable=unused-argument
        return False


@admin.register(FeedbackTag)
class FeedbackTagAdmin(ColorTagAdmin):
    fields = ColorTagAdmin.fields + (
        'course',
    )


admin.site.register(ContextTag, admin.ModelAdmin)
