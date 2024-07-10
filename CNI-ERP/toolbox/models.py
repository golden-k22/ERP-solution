from multiprocessing import Manager
from django.db import models
from jsignature.mixins import JSignatureFieldsMixin

from project.models import Project

def content_attend_signature(instance, filename):
    return 'toolbox/attendees/signature/{1}'.format(instance, filename)
def content_file_toolbox(instance, filename):
    return 'toolbox/photo/{1}'.format(instance, filename)
# Create your models here.
class ToolBox(models.Model):
    supervisor = models.CharField(max_length=255, blank=True, null=True)
    tbm_no = models.CharField(max_length=255, blank=True, null=True)
    project_no = models.CharField(max_length=255, blank=True, null=True)
    project_name = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to=content_file_toolbox, blank=True)

    def __str__(self):
        return self.tbm_no

    class Meta:
        db_table = "tb_tbm"

class ToolBoxItem(models.Model):
    Health = 'Health'
    Worksite_Specific = 'Worksite Specific'
    Objective = (
        ('Health', 'Health'),
        ('Worksite Specific', 'Worksite Specific'),
    )
    Engineer = "Engineer"
    Manager = (
        ('Engineer', 'Engineer'),
        ('Supervisor', 'Supervisor'),
    )
    
    # activity = models.CharField(max_length=255, blank=True, null=True)
    objective = models.CharField(max_length=100, choices=Objective, default=Health)
    description = models.CharField(max_length=255, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    manager = models.CharField(max_length=100, choices=Manager, default=Engineer)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    # def __str__(self):
    #     return self.id

    class Meta:
        db_table = "tb_tbm_item"

class ToolBoxLogItem(models.Model):
    Health = 'Health'
    Worksite_Specific = 'Worksite Specific'
    Objective = (
        ('Health', 'Health'),
        ('Worksite Specific', 'Worksite Specific'),
    )
    Engineer = "Engineer"
    Manager = (
        ('Engineer', 'Engineer'),
        ('Supervisor', 'Supervisor'),
    )
    
    activity = models.CharField(max_length=255, blank=True, null=True)
    objective = models.CharField(max_length=100, choices=Objective, default=Health)
    description = models.CharField(max_length=255, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    manager = models.CharField(max_length=100, choices=Manager, default=Engineer)
    toolbox = models.ForeignKey(ToolBox, on_delete=models.SET_NULL, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.activity

    class Meta:
        db_table = "tb_tbm_log_item"

class ToolBoxAttendeesLog(JSignatureFieldsMixin):
    name = models.CharField(max_length=255, blank=True, null=True)
    nric = models.CharField(max_length=255, blank=True, null=True)
    signature_image = models.ImageField(upload_to=content_attend_signature, blank=True)
    toolbox = models.ForeignKey(ToolBox, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "tb_tbm_attendeeslog"

class ToolBoxObjective(models.Model):
    classify = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.classify

    class Meta:
        db_table = "tb_tbm_objective"

class ToolBoxDescription(models.Model):
    description = models.CharField(max_length=255,null=False, blank=False)
    objective = models.ForeignKey(ToolBoxObjective, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.description

    class Meta:
        db_table = "tb_tbm_description"