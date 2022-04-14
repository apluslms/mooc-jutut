"""
This file contains strings that do not have translations in libraries,
but we still need them to be translated.

This is easier method than finding some hard way to add translations
for specifig files or modules from libaries to project locales files.
"""
from django.utils.translation import gettext_lazy as _

_('This field is required.')
