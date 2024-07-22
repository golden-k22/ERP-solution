from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG")

ALLOWED_HOSTS = ["*","165.232.170.117", "localhost"]
DATA_UPLOAD_MAX_MEMORY_SIZE = 20971520
#MySQL Database Engine
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv("DJANGO_DATABASE_NAME"),
        'USER': os.getenv("DJANGO_DATABASE_USER"),
        'PASSWORD': os.getenv("DJANGO_DATABASE_PASSWORD"),
        'HOST': os.getenv("DJANGO_DATABASE_HOST"),
        'PORT': '3306',
        'OPTIONS': {
            'sql_mode': 'traditional',
        }
    }
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = (
    BASE_DIR / "static",
)

MEDIA_URL = '/media/'
MEDIA_ROOT = (BASE_DIR / "media")

CORS_ORIGIN_ALLOW_ALL = True

LOGIN_REDIRECT_URL = 'dashboard'

LOGIN_URL = 'view_login'

LOGOUT_REDIRECT_URL = 'view_login'


DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_EMAIL")

EMAIL_USE_TLS = True
# EMAIL_USE_SSL = True
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD")

# Email section
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

INSTALLED_APPS = [
    'django_apscheduler',
    'django_crontab',
    'admin_interface',
    'colorfield',
    'cities_light',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'import_export',
    'notifications',
    'accounts',
    'dashboard',
    'expenseclaim',
    'sales',
    'project',
    'inventory',
    'userprofile',
    'maintenance',
    'corsheaders',
    'siteprogress',
    'toolbox',
    'jsignature',
    'activity_log',
    'django.contrib.humanize',
    "calendarapp.apps.CalendarappConfig",
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'activity_log.middleware.ActivityLogMiddleware',

    'erpSolution.SessionMiddleware.SessionMiddleware'
]
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.111.115:80"
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]


CRONJOBS = [
    ('*/2 * * * *', 'erpSolution.dashboard.schedule_cron_job')
]
DJANGO_NOTIFICATIONS_CONFIG = { 'USE_JSONFIELD': True}

ACTIVITYLOG_AUTOCREATE_DB = False
# Log anonymous actions?
ACTIVITYLOG_ANONYMOUS = True
# Only this methods will be logged
ACTIVITYLOG_METHODS = ('POST', 'DELETE')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR,'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],

            'libraries':{
                'custom_tags': 'project.templatetags.custom_tags',
            }
        },
    },
]

SESSION_EXPIRE_AT_BROWSER_CLOSE = False     # opional, as this will log you out when browser is closed
SESSION_COOKIE_AGE = 1800                   # 0r 30 * 60, same thing
SESSION_SAVE_EVERY_REQUEST = True          # Will prevent from logging you out after 300 seconds
