import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from calendarapp import views

scheduler = BackgroundScheduler(timezone=os.getenv("TIME_ZONE"))
scheduler.start()


def checking_notification():
    views.task()


# scheduler.add_job(checking_notification, 'interval', seconds=3)
scheduler.add_job(checking_notification,
                  trigger=CronTrigger(hour="00", minute="00", timezone=os.getenv("TIME_ZONE")),
                  id="checking_notification",
                  max_instances=1,
                  replace_existing=True, )
