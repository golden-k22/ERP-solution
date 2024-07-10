from django.db import models
from project.models import Project
from accounts.models import Uom

# Create your models here.

class SiteProgress(models.Model):
    description = models.CharField(max_length=500, blank=True, null=True)
    qty = models.IntegerField(default=0)
    date = models.DateField(null=True, blank=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    updated_by = models.CharField(max_length=100, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.description
    class Meta:
        db_table = "tb_site_progress"


class ProgressLog(models.Model):
    description = models.CharField(max_length=255, blank=True, null=True)
    qty = models.IntegerField(default=0)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    allocation = models.CharField(max_length=255, blank=True, null=True)
    cummulative_qty = models.IntegerField(default=0)
    cummulative_percent = models.IntegerField(default=0)
    updated_by = models.CharField(max_length=100, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.description
    class Meta:
        db_table = "tb_site_progress_log"


class SiteProgressPlan(models.Model):
    description = models.CharField(max_length=500, blank=True, null=True)
    qty = models.IntegerField(default=0)
    date = models.DateField(null=True, blank=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    updated_by = models.CharField(max_length=100, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.description
    class Meta:
        db_table = "tb_site_progress_plan"
class SiteProgressRepeated(models.Model):
    date = models.DateField(null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.project
    class Meta:
        db_table = "tb_site_progress_repeated"