"""
Django settings

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

import os, warnings
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Critical (override in local_settings.py)
###############################################################################
DEBUG = False
SECRET_KEY = None
ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)
#SERVER_EMAIL = 'root@'
ALLOWED_HOSTS = ["*"]
###############################################################################


# Content (may override in local_settings.py)
#
# Any templates can be overridden by copying into
# local_templates/possible_path/template_name.html
###############################################################################

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',

    'feedback',
]

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'local_templates'),
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                "django.core.context_processors.debug",
                "django.core.context_processors.i18n",
                "django.core.context_processors.media",
                "django.core.context_processors.static",
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ROOT_URLCONF = 'jutut.urls'
WSGI_APPLICATION = 'jutut.wsgi.application'


# Database (override in local_settings.py)
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mooc_jutut_prod',
        'USER': 'mooc_jutut_user',
        #'PASSWORD': 'mypassword',
        #'HOST': '127.0.0.1',
        #'PORT': '5432',
    },
}


# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'EET'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'assets'),
)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Logging
# https://docs.djangoproject.com/en/1.7/topics/logging/
LOGGING = {
  'version': 1,
  'disable_existing_loggers': False,
  'formatters': {
    'verbose': {
      'format': '[%(asctime)s: %(levelname)s/%(module)s] %(message)s'
    },
  },
  'handlers': {
    'console': {
      'level': 'DEBUG',
      'class': 'logging.StreamHandler',
      'stream': 'ext://sys.stdout',
      'formatter': 'verbose',
    },
    'email': {
      'level': 'ERROR',
      'class': 'django.utils.log.AdminEmailHandler',
    },
  },
  'loggers': {
    '': {
      'level': 'INFO',
      'handlers': ['email', 'console'],
      'propagate': True
    },
  },
}


###############################################################################
#
# Settings logic to handle local settings and any reactions to them
#

# Overrides and appends settings defined in local_settings.py
try:
    from local_settings import *
except ImportError:
    try:
        from jutut.local_settings import *
    except ImportError:
        # make a warning that there is no local_settings, but ignore the exception
        warnings.warn("Couldn't find local_settings.py from project root nor under aplus/")
        pass

if not SECRET_KEY:
    try:
        from .secret_key import SECRET_KEY
    except ImportError:
        from lib.helpers import create_secret_key_file
        settings_dir = os.path.abspath(os.path.dirname(__file__))
        key_filename = os.path.join(settings_dir, 'secret_key.py')
        create_secret_key_file(key_filename)
        warnings.warn("SECRET_KEY not defined in local_settings.py, created one in %s" % (key_filename,))
        del settings_dir
        del create_secret_key_file
        del key_filename
        from .secret_key import SECRET_KEY
