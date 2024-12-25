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


# # Email section
# # EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")
# EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER")
# EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD")

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')


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
    
    'django_otp',
    'django_otp.plugins.otp_totp',  # Time-based OTP
    'django_otp.plugins.otp_static',  # Static OTP
    # 'django_otp.plugins.otp_hotp',  # Counter-based OTP (if needed)
    'django_otp.plugins.otp_email',
    'two_factor',
    'two_factor.plugins.email',

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
    'django_otp.middleware.OTPMiddleware', 

    'erpSolution.SessionMiddleware.DynamicTwoFactorRememberMiddleware',
    'erpSolution.SessionMiddleware.AutoLogoutMiddleware',
    # 'erpSolution.SessionMiddleware.SessionMiddleware',

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
# Use database-backed sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False     # opional, as this will log you out when browser is closed
# SESSION_COOKIE_AGE = 1800                   # 0r 30 * 60, same thing
# SESSION_SAVE_EVERY_REQUEST = True          # Will prevent from logging you out after 300 seconds
AUTO_LOGOUT_DELAY = 30 * 60      # Used custom logout middleware for auto logout.

# Enable the "remember me" cookie for two-factor authentication
TWO_FACTOR_REMEMBER_COOKIE = True
TWO_FACTOR_REMEMBER_COOKIE_AGE = 86400  # 1 day

TIME_ZONE = os.getenv('TIME_ZONE')
USE_TZ = True  # Ensure that timezone support is enabled