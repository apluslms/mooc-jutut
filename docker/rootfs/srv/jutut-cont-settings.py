DEBUG = True
SECRET_KEY = 'not a very secret key'
ADMINS = (
)
#ALLOWED_HOSTS = ["*"]

STATIC_ROOT = '/local/jutut/static/'
MEDIA_ROOT = '/local/jutut/media/'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'jutut',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    },
    'jinja2mem': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'jinja2mem',
    },
}

CELERY_BROKER_URL = "amqp://"

LOGGING['loggers'].update({
    '': {
        'level': 'INFO',
        'handlers': ['debug_console'],
        'propagate': True,
    },
    'aplus_client.client': {
        'level': 'DEBUG',
    },
    'django_lti_login': {
        'level': 'DEBUG',
    },
    #'django.db.backends': {
    #    'level': 'DEBUG',
    #},
    'feedback': {
        'level': 'DEBUG',
        'propagate': True,
    }
})

JUTUT['SERVICE_STATUS'] = (
    #('PostgreSQL', ('s6-svstat', '/run/s6/services/postgresql/')),
    #('RabbitMQ', ('s6-svstat', '/run/s6/services/rabbitmq/')),
    #('Celery workers', ('s6-svstat', '/run/s6/services/jutut-celery-worker/')),
    #('Celery beat', ('s6-svstat', '/run/s6/services/jutut-celery-beat/')),
)

# kate: space-indent on; indent-width 4;
# vim: set expandtab ts=4 sw=4:
