import os

from django.contrib import admin

# Register your models here.
from project.models import Project, OT, Bom, Team, BomLog, ProjectFile, Sr, Do, Pc, DOSignature

admin.site.register(Project)
admin.site.register(OT)
admin.site.register(Bom)
admin.site.register(BomLog)
admin.site.register(Team)
admin.site.register(ProjectFile)
admin.site.register(Sr)
admin.site.register(Do)
admin.site.register(Pc)
admin.site.register(DOSignature)

# For notification
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from project import views

scheduler = BackgroundScheduler(timezone=os.getenv("TIME_ZONE"))
scheduler.start()


def checking_notification():
    print("--------------- Project scheduler started. --------------")
    views.task()


# scheduler.add_job(checking_notification, 'interval', seconds=3)
scheduler.add_job(checking_notification,
                  trigger=CronTrigger(hour="00", minute="3", timezone=os.getenv("TIME_ZONE")),
                  id="checking_notification",
                  max_instances=1,
                  replace_existing=True,)