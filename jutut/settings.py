"""
Django settings

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/

For list of default values:
https://github.com/django/django/blob/master/django/conf/global_settings.py
"""

from os.path import abspath, dirname, join
from django.utils.translation import ugettext_lazy as _


## Base options
BASE_DIR = dirname(dirname(abspath(__file__)))
EMAIL_SUBJECT_PREFIX = '[MOOC-Jutut] '
WSGI_APPLICATION = 'jutut.wsgi.application'

## Jutut options (do not effect django framework)
# Automatically accept with best grade feedbacks that do not have any required
# text fields and no answer in option text fields
JUTUT_AUTOACCEPT_ON = True
# minimum length in text field to count it as filled
JUTUT_TEXT_FIELD_MIN_LENGTH = 2
# Show only best grade for feedbacks that do not contain any required text fields
JUTUT_OBLY_ACCEPT_ON = True


## Core django definitions: applications, middlewares, templates, auth
INSTALLED_APPS = [
    # Django libs
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.postgres',
    # 3rd party libs
    'django_jinja',
    'django_jinja.contrib._humanize',
    'bootstrapform',
    'bootstrapform_jinja',
    # js/css/html resources
    'js_jquery_toggle',
    # libs
    'django_lti_login',
    'aplus_client',
    'dynamic_forms',
    'django_colortag',
    'django_dictiterators',
    # project apps
    'accounts',
    'feedback',
]

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Any templates can be overridden by copying into
# local_templates/module/template_name.html
TEMPLATES = [
    {
        # Used for in project jinja files
        'NAME': 'Jinja2-templates_j2-html',
        'BACKEND': 'django_jinja.backend.Jinja2',
        'DIRS': [
            join(BASE_DIR, 'local_templates_j2'),
            join(BASE_DIR, 'templates_j2'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            # Match the template names ending in .html but not the ones in the admin folder.
            'match_extension': None, # '.jinja', '.html',
            #'match_regex': r'^(?!admin/).*',
            'app_dirname': 'templates_j2',
            'newstyle_gettext': True,
            'extensions': [
                'jinja2.ext.i18n',
                'django_jinja.builtins.extensions.CsrfExtension',
                #'django_jinja.builtins.extensions.CacheExtension',
                'django_jinja.builtins.extensions.TimezoneExtension',
                'django_jinja.builtins.extensions.UrlsExtension',
                'django_jinja.builtins.extensions.StaticFilesExtension',
                #'django_jinja.builtins.extensions.DjangoFiltersExtension',
                'r_django_essentials.jinja2.extensions.I18nExtrasExtension',
            ],
            'bytecode_cache': {
                'name': 'jinja2mem',
                'backend': 'django_jinja.cache.BytecodeCache',
                'enabled': True,
            },
        }
    },
    {
        # Takes care of '.jinja' tempaltes in tempaltes folder
        'NAME': 'Jinja2-templates-jinja',
        'BACKEND': 'django_jinja.backend.Jinja2',
        'DIRS': [
            join(BASE_DIR, 'local_templates'),
            join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            # Match the template names ending in .html but not the ones in the admin folder.
            'match_extension': '.jinja',
            'app_dirname': 'templates',
            'newstyle_gettext': True,
            'extensions': [
                'jinja2.ext.i18n',
                'django_jinja.builtins.extensions.CsrfExtension',
                'django_jinja.builtins.extensions.TimezoneExtension',
            ],
            'bytecode_cache': {
                'name': 'jinja2mem',
                'backend': 'django_jinja.cache.BytecodeCache',
                'enabled': True,
            },
        }
    },
    {
        # To support DjangoTemplate files
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            join(BASE_DIR, 'local_templates'),
            join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': (
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ),
        },
    },
]

ROOT_URLCONF = 'jutut.urls'
LOGIN_REDIRECT_URL = '/manage/'


## Database (override in local_settings.py)
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mooc_jutut_prod',
        #'USER': 'username',
        #'PASSWORD': 'mypassword',
        #'HOST': '127.0.0.1',
        #'PORT': '5432',
    },
}


## Authentication
AUTHENTICATION_BACKENDS = [
    'django_lti_login.backends.LTIAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_USER_MODEL = 'accounts.JututUser'
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator' },
]

# LTI login: allow only course staff to enter using lti login
AUTH_LTI_LOGIN = {
    'ACCEPTED_ROLES': ('Instructor', 'TeachingAssistant'),
    'STAFF_ROLES': None, # No one over LTI will get staff rights.
}


## Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/
LANGUAGE_CODE = 'en'
TIME_ZONE = 'EET'
USE_TZ = True
USE_I18N = True # Use localization
USE_L10N = True # Use localization for dates and times

LANGUAGES = (
    ('fi', _('Finnish')),
    ('en', _('English')),
)

LOCALE_PATHS = (
    'locale',
)


## Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATICFILES_DIRS = (
    join(BASE_DIR, 'assets'),
)
STATIC_URL = '/static/'
STATIC_ROOT = join(BASE_DIR, 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = join(BASE_DIR, 'media')


## Cache
# https://docs.djangoproject.com/en/1.9/topics/cache/
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211',
    },
    'jinja2mem': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'jinja2mem',
    },
}


## Logging
# https://docs.djangoproject.com/en/1.7/topics/logging/
LOGGING = {
  'version': 1,
  'disable_existing_loggers': False,
  'formatters': {
    'verbose': {
      'format': '[%(asctime)s: %(levelname)s/%(module)s] %(message)s'
    },
    'colored': {
      '()': 'r_django_essentials.logging.SourceColorizeFormatter',
      'format': '[%(asctime)s: %(levelname)8s %(name)s] %(message)s',
      'colors': {
        'aplus_client.client': {'fg': 'red', 'opts': ('bold',)},
        'django_lti_login': {'fg': 'yellow'},
        'feedback.receivers': {'fg': 'yellow'},
        'django.db.backends': {'fg': 'cyan'},
      },
    },
  },
  'filters': {
    'require_debug_true': {
      '()': 'django.utils.log.RequireDebugTrue',
    }
  },
  'handlers': {
    'debug_console': {
      'level': 'DEBUG',
      'filters': ['require_debug_true'],
      'class': 'logging.StreamHandler',
      'stream': 'ext://sys.stdout',
      'formatter': 'colored',
    },
    'console': {
      'level': 'INFO',
      'class': 'logging.StreamHandler',
      'stream': 'ext://sys.stdout',
      'formatter': 'verbose',
    },
    'mail': {
      'level': 'ERROR',
      'class': 'django.utils.log.AdminEmailHandler',
    },
  },
  'loggers': {
    '': {
      'level': 'INFO',
      'handlers': ['console'],
      'propagate': True
    },
    'requests': { 'level': 'WARNING' },
  },
}


## Django filters
# https://django-filter.readthedocs.io/en/latest/ref/settings.html
FILTERS_HELP_TEXT_EXCLUDE = False
FILTERS_HELP_TEXT_FILTER = False


## Celery
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULE = {
    'feedback.schedule_failed': {
        # check database for failed uploads that don't appear to be in queue
        'task': 'feedback.schedule_failed',
        'schedule': 30 * 60, # every 30 minutes
        'args': (),
    },
}


################################################################################
# Do some updates and additions to above settings
from r_django_essentials.conf import update_settings, update_settings_from_module

# Load local settings for celery (INSTALLATION tells to add rabbitmq password in this file).
update_settings_from_module(__name__, 'local_settings_celery')

# Load settings from local_settings, secret_key, environment.
# Make sure app dependencies are included etc.
# USe cache template loader in production
update_settings(__name__)
