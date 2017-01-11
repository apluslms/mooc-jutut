from django.contrib import admin

from .models import (
    Form,
)

if not Form._meta.abstract:
    admin.site.register(Form)
