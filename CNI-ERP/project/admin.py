import os

from django.contrib import admin

# Register your models here.
from project.models import Project, OT, Bom, Team, BomLog, ProjectFile, Sr, Do, Pc, DOSignature, InvoiceFormat, WorklogCheckSchedule

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
admin.site.register(InvoiceFormat)
admin.site.register(WorklogCheckSchedule)

# For notification
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from project import views

scheduler = BackgroundScheduler(timezone=os.getenv("TIME_ZONE"))
scheduler.start()


def checking_notification():
    print("--------------- Project scheduler started. --------------")
    views.task()

def checking_worklog():
    print("--------------- Worklog scheduler started. --------------")
    views.worklog_task()

def checking_schedule():
    print("--------------- Schedule message by whatsApp. --------------")
    views.scheduleing_task()


# scheduler.add_job(checking_notification, 'interval', seconds=3)
scheduler.add_job(checking_notification,
                  trigger=CronTrigger(hour="00", minute="01", timezone=os.getenv("TIME_ZONE")),
                  id="checking_notification",
                  max_instances=1,
                  replace_existing=True,)

scheduler.add_job(checking_worklog,
                  trigger=CronTrigger(hour="11", minute="00", timezone=os.getenv("TIME_ZONE")),
                  id="checking_worklog",
                  max_instances=1,
                  replace_existing=True,)

scheduler.add_job(checking_schedule,
                  trigger=CronTrigger(hour="11", minute="00", timezone=os.getenv("TIME_ZONE")),
                  id="checking_schedule",
                  max_instances=1,
                  replace_existing=True,)