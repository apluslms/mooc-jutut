from django.contrib import admin

from .models import (
    Token,
    JututUser,
)

admin.site.register(Token)
admin.site.register(JututUser)
