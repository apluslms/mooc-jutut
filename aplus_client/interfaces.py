import logging
from functools import wraps, partial
from datetime import datetime, timezone


DATETIME_JSON_FMT = '%Y-%m-%dT%H:%M:%S.%f%z'

logger = logging.getLogger('aplus_client.interfaces')


def none_on_error(*args, exceptions=None, silent=False):
    if not args:
        return partial(none_on_error, exceptions=exceptions)
    if len(args) > 1 or (isinstance(args[0], type) and issubclass(args[0], Exception)):
        return partial(none_on_error, exceptions=args)

    func = args[0]
    exceptions = tuple(set([AttributeError] + (list(exceptions) if exceptions else [])))

    @wraps(func)
    def wrap(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            if not silent:
                logger.info("interface %s raised exception %s", func.__name__, e)
            return None
    return wrap


class GraderInterface2:
    def __init__(self, data):
        self.data = data

    @property
    @none_on_error
    def exercise(self):
        return self.data.exercise

    @property
    @none_on_error(silent=True)
    def exercise_api(self):
        return self.data.exercise.url

    @property
    @none_on_error
    def course(self):
        return self.data.exercise.course

    @property
    @none_on_error
    def language(self):
        return self.data.exercise.course.language or None

    @property
    @none_on_error(KeyError)
    def form_spec(self):
        return self.data.exercise.exercise_info.get_item('form_spec')

    @property
    @none_on_error(KeyError)
    def form_i18n(self):
        return self.data.exercise.exercise_info.get_item('form_i18n')

    @property
    @none_on_error
    def submission_id(self):
        return self.data.submission.id

    @property
    @none_on_error
    def submitters(self):
        return self.data.submission.submitters

    @property
    @none_on_error(ValueError)
    def submission_time(self):
        time = self.data.submission.submission_time
        # TODO: move parsing to helper (though, fixed in py3.7)
        if not time:
            return None
        if time[-1] == 'Z': # .000X -> .000+0000
            time = time[:-1] + '+0000'
        if time[-3] == ':': # .000+02:00 -> 0.00+0200
            time = time[:-3] + time[-2:]
        return datetime.strptime(time, DATETIME_JSON_FMT).astimezone(timezone.utc)

    @property
    @none_on_error(KeyError)
    def html_url(self):
        return self.data.submission.get_item('html_url')

    @property
    def feedback_response_seen(self):
        return self.data.feedback_response_seen
