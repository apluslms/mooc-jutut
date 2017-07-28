from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    name = 'feedback'

    def ready(self):
        # load some packages to connect signals
        from . import receivers  # NOQA
