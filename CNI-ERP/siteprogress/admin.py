import os

from django.contrib import admin
from siteprogress.models import SiteProgress, ProgressLog
# Register your models here.

admin.site.register(SiteProgress)
admin.site.register(ProgressLog)


# For check site progress plans
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from siteprogress import views

scheduler = BackgroundScheduler()
scheduler.start()


def checking_plans():
    views.check_plans()
scheduler.add_job(checking_plans,
                  trigger=CronTrigger(hour="00", minute="00", timezone=os.getenv("TIME_ZONE")),
                  id="checking_plans",
                  max_instances=1,
                  replace_existing=True,)