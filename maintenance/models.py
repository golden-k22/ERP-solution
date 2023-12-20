from django.db import models
from accounts.models import User
from sales.models import Company, Contact, Quotation
from accounts.models import Uom
from jsignature.mixins import JSignatureFieldsMixin
import os

# Create your models here.
def content_file(instance, filename):
    return 'maintenance/%s/file/%s' % (instance.maintenance.main_no, filename)

def content_file_main_service(instance, filename):
    return 'maintenance/%s/service/%s' % (instance.maintenance.main_no, filename)

def content_file_srsignature(instance, filename):
    return 'maintenance/%s/srsignature/%s' % (instance.maintenance.main_no, filename)

class Maintenance(models.Model):
    main_no = models.CharField(unique=True,max_length=100, blank=True, null=True)
    customer = models.CharField(max_length=100, blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    in_incharge = models.CharField(max_length=50, blank=True, null=True)
    main_status = models.CharField(max_length=255, blank=True, null=True)
    company_nameid = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)
    worksite_address = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.ForeignKey(Contact, on_delete=models.SET_NULL, blank=True, null=True)
    site_incharge = models.CharField(max_length=50, blank=True, null=True)
    site_tel = models.CharField(max_length=50, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    quot_no = models.CharField(max_length=100, blank=True, null=True)
    proj_incharge = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    tel = models.CharField(max_length=50, blank=True, null=True)
    fax = models.CharField(max_length=50, blank=True, null=True)
    RE = models.TextField(blank=True, null=True)
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.main_no
    class Meta:
        db_table = "tb_maintenance"

class MaintenanceFile(models.Model):
    name = models.CharField(max_length=250,unique=True, blank=True, null=True)
    document = models.FileField(upload_to=content_file,null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    date = models.DateField(null=True, blank=True)
    maintenance = models.ForeignKey(Maintenance, on_delete=models.SET_NULL, blank=True, null=True)

    def filename(self):
        return os.path.basename(self.document.name)
    def __str__(self):
        return self.name
    class Meta:
        db_table = "tb_maintenance_file"

class MainSr(models.Model):
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
    )
    #Purpose
    New_Project	 = "New Project"
    Purpose = (
        ('New Project', 'New Project'),
        ('Existing Project', 'Existing Project'),
        ('Maintenance', 'Maintenance'),
        ('Troubleshooting', 'Troubleshooting'),
    )

    sr_no = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, choices=Status, default=Open)
    date = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to=content_file_main_service,null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="main_created_by")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    srtype = models.CharField(max_length=100, choices=Type, null=True)
    srsystem = models.CharField(max_length=100, choices=System, null=True)
    srpurpose = models.CharField(max_length=100, choices=Purpose, null=True)
    time_in = models.DateTimeField(blank=True, null=True)
    time_out = models.DateTimeField(blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    maintenance = models.ForeignKey(Maintenance, on_delete=models.SET_NULL, blank=True, null=True)
    invoice_no=models.CharField(max_length=8, blank=True, null=True)

    def filename(self):
        return os.path.basename(self.document.name)
    def __str__(self):
        return self.sr_no
    class Meta:
        db_table = "tb_maintenance_sr"

class MainSrItem(models.Model):
    description = models.TextField(blank=True, null=True)
    qty = models.IntegerField(default=0, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    maintenance = models.ForeignKey(Maintenance, on_delete=models.SET_NULL, blank=True, null=True)
    sr = models.ForeignKey(MainSr, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.description
    class Meta:
        db_table = "tb_maintenance_sr_items"

class MainSRSignature(JSignatureFieldsMixin):
    name = models.CharField(max_length=250, blank=True, null=True)
    nric = models.CharField(max_length=250, blank=True, null=True)
    maintenance = models.ForeignKey(Maintenance, on_delete=models.SET_NULL, blank=True, null=True)
    sr = models.ForeignKey(MainSr, on_delete=models.SET_NULL, blank=True, null=True)
    signature_image = models.ImageField(upload_to=content_file_srsignature,null=True, blank=True)
    update_date = models.DateField(null=True, blank=True)
    def __str__(self):
        return self.name
    class Meta:
        db_table = "tb_maintenance_sr_signature"

class Device(models.Model):
    hardware_code = models.CharField(max_length=100, blank=True, null=True, unique=True)
    hardware_desc = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)
    licensing_date = models.DateField(null=True, blank=True)
    qty = models.IntegerField(default=0)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    maintenance = models.ForeignKey(Maintenance, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.hardware_desc
    class Meta:
        db_table = "tb_maintenance_device"
        ordering = ['-hardware_desc']

class Schedule(models.Model):
   
    Reminder = (
        ('1', 'Before 1 Day'),
        ('3', 'Before 3 Days'),
        ('7', 'Before 1 Week'),
        ('14', 'Before 2 Weeks'),
        ('30', 'Before 1 Month'),
    )
    date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    reminder = models.CharField(max_length=255, choices=Reminder, default='3')
    maintenance = models.ForeignKey(Maintenance, on_delete=models.SET_NULL, blank=True, null=True)
    def get_reminder_str(self):
        return self.get_reminder_display()


    class Meta:
        db_table = "tb_maintenance_reminder"