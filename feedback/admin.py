from django.contrib import admin
from django_colortag.admin import ColorTagAdmin

from .models import (
    FeedbackTag,
)


class FeedbackTagAdmin(ColorTagAdmin):
    fields = ColorTagAdmin.fields + (
        'course',
    )

admin.site.register(FeedbackTag, FeedbackTagAdmin)
