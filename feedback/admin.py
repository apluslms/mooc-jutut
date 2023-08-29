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


class CachedAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None): # pylint: disable=unused-argument
        return False


class FeedbackTagAdmin(ColorTagAdmin):
    fields = ColorTagAdmin.fields + (
        'course',
    )


admin.site.register(Student, CachedAdmin)
admin.site.register(Course, CachedAdmin)
admin.site.register(Exercise, CachedAdmin)
admin.site.register(Feedback, CachedAdmin)
admin.site.register(FeedbackTag, FeedbackTagAdmin)
admin.site.register(ContextTag, admin.ModelAdmin)
