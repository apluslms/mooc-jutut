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
from django.utils.translation import gettext_lazy as _


## Base options
BASE_DIR = dirname(dirname(abspath(__file__)))
EMAIL_SUBJECT_PREFIX = '[MOOC-Jutut] '
WSGI_APPLICATION = 'jutut.wsgi.application'
ALLOWED_HOSTS = ["*"]

## Jutut options
JUTUT = {
    # minimum length in text field to count it as filled
    'TEXT_FIELD_MIN_LENGTH': 2,
    # List of services to show in service status page with commands to get the status
    'SERVICE_STATUS': (
        ('Django gunicorn', ('systemctl', 'status', 'mooc-jutut-gunicorn')),
        ('RabbitMQ', ('systemctl', 'status', 'rabbitmq-server')),
        ('Celery workers', ('systemctl', 'status', 'mooc-jutut-celery')),
        ('Celery beat', ('systemctl', 'status', 'mooc-jutut-celerybeat')),
    ),
}


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
    'django_filters',
    # js/css/html resources
    'js_jquery_toggle',
    # libs
    'django_lti_login',
    'aplus_client',
    'dynamic_forms',
    'django_colortag',
    'django_dictiterators',
    # project apps
    'core',
    'accounts',
    'feedback',
    'timeusage'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
                'r_django_essentials.jinja2.extensions.CryptoExtension',
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

# Default model primary key field
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


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

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'core.vstorage.VirtualFinder',
)

RENDERED_STATIC_FILES = {
    'err_404.html': (
        'core/static_error_page.html',
        {
            'code': '404',
            'title': 'Not Found',
            'glyph': 'remove',
            'desc': (
                "Requested page is not available.",
                "Hakemaasi sivua ei löytynyt.",
            ),
        }
    ),
    'err_500.html': (
        'core/static_error_page.html',
        {
            'code': '500',
            'title': 'Internal Server Error',
            'glyph': 'fire',
            'desc': (
                "The web server is returning an internal error. There is something wrong with it!",
                "Web palvelu palauttaa sisäisen virheen. Se on jotenkin rikki!",
            ),
        }
    ),
    # maintenance
    'err_503.html': (
        'core/static_error_page.html',
        {
            'code': '503',
            'title': 'Service Unavailable',
            'glyph': 'wrench',
            'glyph_color': "#5cb85c",
            'desc': (
                "The web server is currently undergoing some maintenance. We'll be back shortly!",
                "Palvelussa on väliaikainen huoltokatko. Palvelu palaa käyttöön pian!"
            ),
        }
    ),
}

## Cache
# https://docs.djangoproject.com/en/1.9/topics/cache/
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
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
from os import environ
from r_django_essentials.conf import *

# Load local settings for celery (INSTALLATION tells to add rabbitmq password in this file).
update_settings_from_module(__name__, 'local_settings_celery', quiet=True)

# Local settings
update_settings_with_file(__name__,
                          environ.get('JUTUT_LOCAL_SETTINGS', 'local_settings'),
                          quiet='JUTUT_LOCAL_SETTINGS' in environ)

# Settings from environment
update_settings_from_environment(__name__, 'JUTUT_')

# Ensure secret key (if above files defined it, then this does nothing)
update_secret_from_file(__name__, environ.get('JUTUT_SECRET_KEY_FILE', 'secret_key'))

# Resolve app dependencies, check context processors and so on...
update_settings_fixes(__name__)
