from django.db import models
from accounts.models import User
from jsignature.mixins import JSignatureFieldsMixin

from sales.models import Company, Contact, Quotation, Scope
from accounts.models import Uom
import os

def content_file_delivery(instance, filename):
    return 'project/%s/delivery/%s' % (instance.project.proj_id, filename)

def content_file(instance, filename):
    return 'project/%s/file/%s' % (instance.project.proj_id, filename)

def content_file_service(instance, filename):
    return 'project/%s/service/%s' % (instance.project.proj_id, filename)

def content_file_progress(instance, filename):
    return 'project/progress/{1}'.format(instance, filename)

def content_file_dosignature(instance, filename):
    return 'project/%s/dosignature/%s' % (instance.project.proj_id, filename)

def content_file_srsignature(instance, filename):
    return 'project/%s/srsignature/%s' % (instance.project.proj_id, filename)

def content_file_pcsignature(instance, filename):
    return 'project/%s/pcsignature/%s' % (instance.project.proj_id, filename)

# Create your models here.
class Project(models.Model):
    Status = (
        ('Open', 'Open'),
        ('On-going', 'On-going'),
        ('Completed', 'Completed'),
        ('Closed', 'Closed'),
        ('Old Record', 'Old Record'),
    )
    proj_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    qtt_id = models.CharField(max_length=100, blank=True, null=True)
    company_nameid = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)
    worksite_address = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.ForeignKey(Contact, on_delete=models.SET_NULL, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    tel = models.CharField(max_length=50, blank=True, null=True)
    fax = models.CharField(max_length=50, blank=True, null=True)
    site_incharge = models.CharField(max_length=50, blank=True, null=True)
    site_tel = models.CharField(max_length=50, blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    RE = models.TextField(blank=True, null=True)
    proj_incharge = models.CharField(max_length=100, blank=True, null=True)
    proj_status = models.CharField(max_length=255, choices=Status, default="Open")
    proj_name = models.CharField(max_length=100, blank=True, null=True)
    proj_postalcode = models.CharField(max_length=50, blank=True, null=True)
    latitude = models.CharField(max_length=50, blank=True, null=True)
    longitude = models.CharField(max_length=50, blank=True, null=True)
    estimated_mandays = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    variation_order = models.CharField(max_length=100, blank=True, null=True)
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, blank=True, null=True)
    company_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.proj_id
    class Meta:
        db_table = "tb_project"

class OT(models.Model):
    ot_id = models.CharField(max_length=100, blank=True, null=True)
    proj_id = models.CharField(max_length=100, blank=True, null=True)
    RE = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(auto_now_add=False, blank=True, null=True)
    approved_hour = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    ph = models.CharField(max_length=100, blank=True, null=True)
    comment = models.TextField(null=True, blank=True)
    proj_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.proj_id
    class Meta:
        db_table = "tb_ot"

class Do(models.Model):
    Open = 'Open'
    Awarded = 'Signed'
    Status = (
        ('Open', 'Open'),
        ('Signed', 'Signed'),
    )
    do_no = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, choices=Status, default=Open)
    date = models.DateField(null=True, blank=True)
    ship_to = models.TextField(null=True, blank=True)
    document = models.FileField(upload_to=content_file_delivery,null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="do_created_by")
    upload_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="do_upload_by")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    remarks = models.TextField(null=True, blank=True)
    invoice_no=models.CharField(max_length=8, blank=True, null=True)

    def filename(self):
        return os.path.basename(self.document.name)
    def __str__(self):
        return self.do_no
    class Meta:
        db_table = "tb_do"

class Bom(models.Model):
    item_id = models.CharField(max_length=250, blank=True, null=True)
    description = models.CharField(max_length=250, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    ordered_qty = models.IntegerField(default=0)
    brand = models.CharField(max_length=250, blank=True, null=True)
    delivered_qty = models.IntegerField(default=0)
    delivered_po_no = models.CharField(max_length=250, blank=True, null=True)
    date = models.DateField(null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.uom
    class Meta:
        db_table = "tb_bom"

class BomLog(models.Model):
    item_id = models.CharField(max_length=250, blank=True, null=True)
    description = models.CharField(max_length=250, blank=True, null=True)
    date = models.DateField(null=True, blank=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    delivered_qty = models.IntegerField(default=0)
    do_no = models.CharField(max_length=250, blank=True, null=True)
    remark = models.TextField(null=True, blank=True)
    bom = models.ForeignKey(Bom, on_delete=models.SET_NULL, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.uom
    class Meta:
        db_table = "tb_bom_log"

class Team(models.Model):
    emp_no = models.CharField(max_length=250,unique=False, blank=True, null=True)
    first_name = models.CharField(max_length=250, blank=True, null=True)
    last_name = models.CharField(max_length=250, blank=True, null=True)
    role = models.CharField(max_length=250, blank=True, null=True)
    priority = models.IntegerField(default=0)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    def __str__(self):
        return self.emp_no
    class Meta:
        db_table = "tb_team"

class ProjectFile(models.Model):
    name = models.CharField(max_length=250, blank=True, null=True)
    document = models.FileField(upload_to=content_file,null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    date = models.DateField(null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def filename(self):
        return os.path.basename(self.document.name)
    def __str__(self):
        return self.name
    class Meta:
        db_table = "tb_project_file"

class Sr(models.Model):
    Open = 'Open'
    Awarded = 'Signed'
    Status = (
        ('Open', 'Open'),
        ('Signed', 'Signed'),
    )
    #Type 
    Services_Maintenance = "Services & Maintenance"
    Type = (
        ('Services & Maintenance', 'Services & Maintenance'),
        ('Troubleshooting', 'Troubleshooting'),
        ('Testing & Commissioning', 'Testing & Commissioning'),
        ('Handing over', 'Handing over'),
        ('Others, please comment in remarks', 'Others, please comment in remarks'),
    )
    #system
    Structured_Cabling_System = "Structured Cabling System"
    System = (
        ('Structured Cabling System', 'Structured Cabling System'),
        ('IT Network System', 'IT Network System'),
        ('Telephone System', 'Telephone System'),
        ('CCTV System', 'CCTV System'),
        ('Access Control System', 'Access Control System'),
        ('Audio Video Intercom System', 'Audio Video Intercom System'),
        ('Home Automation', 'Home Automation'),
        ('Others, please comment in remarks', 'Others, please comment in remarks'),
    )
    #Purpose
    New_Project	 = "New Project"
    Purpose = (
        ('New Project', 'New Project'),
        ('Existing Project', 'Existing Project'),
        ('Maintenance', 'Maintenance'),
        ('Troubleshooting', 'Troubleshooting'),
        ('Others, please comment in remarks', 'Others, please comment in remarks'),
    )

    sr_no = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, choices=Status, default=Open)
    date = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to=content_file_service,null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="created_by")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="uploaded_by")
    srtype = models.CharField(max_length=100, choices=Type, null=True)
    srsystem = models.CharField(max_length=100, choices=System, null=True)
    srpurpose = models.CharField(max_length=100, choices=Purpose, null=True)
    time_in = models.DateTimeField(blank=True, null=True)
    time_out = models.DateTimeField(blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    invoice_no=models.CharField(max_length=8, blank=True, null=True)

    def filename(self):
        return os.path.basename(self.document.name)
    def __str__(self):
        return self.sr_no
    class Meta:
        db_table = "tb_sr"




class Pc(models.Model):
    Open = 'Open'
    Awarded = 'Signed'
    Status = (
        ('Open', 'Open'),
        ('Signed', 'Signed'),
    )
    pc_no = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, choices=Status, default=Open)
    date = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to=content_file_progress,null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    claim_no = models.IntegerField(null=True, blank=True)
    less_previous_claim = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    payment_cert_no = models.CharField(max_length=100, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    invoice_no=models.CharField(max_length=8, blank=True, null=True)

    def filename(self):
        return os.path.basename(self.document.name)
    def __str__(self):
        return self.pc_no
    class Meta:
        db_table = "tb_pc"

class PcDetail(models.Model):
    project_sum = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    retention_amt = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    date_collect_retention = models.DateField(null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.project_sum
    class Meta:
        db_table = "tb_pc_details"




class DoItem(models.Model):
    description = models.TextField(null=True, blank=True)
    qty = models.IntegerField(default=0, null=True, blank=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    do = models.ForeignKey(Do, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.description
    class Meta:
        db_table = "tb_do_items"

class SrItem(models.Model):
    description = models.TextField(null=True, blank=True)
    qty = models.IntegerField(default=0, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    sr = models.ForeignKey(Sr, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.description
    class Meta:
        db_table = "tb_sr_items"


class DOSignature(JSignatureFieldsMixin):
    name = models.CharField(max_length=250, blank=True, null=True)
    nric = models.CharField(max_length=250, blank=True, null=True)
    update_date = models.DateField(null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    do = models.ForeignKey(Do, on_delete=models.SET_NULL, blank=True, null=True)
    signature_image = models.ImageField(upload_to=content_file_dosignature,null=True, blank=True)
    def __str__(self):
        return self.name
    class Meta:
        db_table = "tb_do_signature"

class SRSignature(JSignatureFieldsMixin):
    name = models.CharField(max_length=250, blank=True, null=True)
    nric = models.CharField(max_length=250, blank=True, null=True)
    update_date = models.DateField(null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    sr = models.ForeignKey(Sr, on_delete=models.SET_NULL, blank=True, null=True)
    signature_image = models.ImageField(upload_to=content_file_srsignature,null=True, blank=True)

    def __str__(self):
        return self.name
    class Meta:
        db_table = "tb_sr_signature"

# class Pc(models.Model):
#     Open = 'Open'
#     Awarded = 'Signed'
#     Status = (
#         ('Open', 'Open'),
#         ('Signed', 'Signed'),
#     )
#     pc_no = models.CharField(max_length=100, blank=True, null=True)
#     status = models.CharField(max_length=100, choices=Status, default=Open)
#     date = models.DateField(null=True, blank=True)
#     document = models.FileField(upload_to=content_file_progress,null=True, blank=True)
#     uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
#     claim_no = models.IntegerField(null=True, blank=True)
#     less_previous_claim = models.CharField(max_length=255, blank=True, null=True)
#     #terms = models.CharField(max_length=255, blank=True, null=True)
#     project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
#
#     def filename(self):
#         return os.path.basename(self.document.name)
#     def __str__(self):
#         return self.pc_no
#     class Meta:
#         db_table = "tb_pc"
# class PcItem(models.Model):
#     description = models.CharField(max_length=250,blank=True, null=True)
#     qty = models.IntegerField(default=0, blank=True, null=True)
#     uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
#     price = models.CharField(max_length=250, blank=True, null=True)
#     done_qty = models.IntegerField(default=0, blank=True, null=True)
#     done_percent = models.FloatField(blank=True, null=True)
#     qty = models.IntegerField(default=0, blank=True, null=True)
#     amount = models.CharField(max_length=250, blank=True, null=True)
#     project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
#     pc = models.ForeignKey(Pc, on_delete=models.SET_NULL, blank=True, null=True)
#
#     def __str__(self):
#         return self.description
#     class Meta:
#         db_table = "tb_pc_items"
# class PCSignature(JSignatureFieldsMixin):
#     name = models.CharField(max_length=250, blank=True, null=True)
#     nric = models.CharField(max_length=250, blank=True, null=True)
#     update_date = models.DateField(null=True, blank=True)
#     project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
#     pc = models.ForeignKey(Pc, on_delete=models.SET_NULL, blank=True, null=True)
#     signature_image = models.ImageField(upload_to=content_file_pcsignature,null=True, blank=True)
#
#     def __str__(self):
#         return self.name
#     class Meta:
#         db_table = "tb_pc_signature"


class ActivitySchedule(models.Model):
    scope = models.ForeignKey(Scope, on_delete=models.SET_NULL, blank=True, null=True)
    qty = models.IntegerField(default=0, blank=True, null=True)
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.scope
    class Meta:
        db_table = "tb_schedule_activities"
class ScheduleUsers(models.Model):
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    shift = models.CharField(max_length=250, blank=True, null=True)
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.project
    class Meta:
        db_table = "tb_schedule_users"

