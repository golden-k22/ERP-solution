from django.db import models

from accounts.models import Uom

# Create your models here.
from project.models import Project
from sales.models import Company


def content_file_material(instance, filename):
    return 'inventory/materials/{1}'.format(instance, filename)

def content_file_assets(instance, filename):
    return 'inventory/assets/{1}'.format(instance, filename)

def content_file_ppe(instance, filename):
    return 'inventory/ppe/{1}'.format(instance, filename)

def content_file_stationary(instance, filename):
    return 'inventory/stationary/{1}'.format(instance, filename)

def content_file_hardware(instance, filename):
    return 'inventory/hardware/{1}'.format(instance, filename)

class Material(models.Model):
    material_code = models.CharField(max_length=100, blank=True, null=True, unique=True)
    product_desc = models.CharField(max_length=100, blank=True, null=True)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    part_number = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    replenish_qty = models.IntegerField(default=0)
    restock_qty = models.IntegerField(default=0)
    stock_qty = models.IntegerField(default=0)
    photo = models.ImageField(upload_to=content_file_material, blank=True)

    def __str__(self):
        return self.product_desc
    class Meta:
        db_table = "tb_material_inventory"
        ordering = ['-product_desc']

class Asset(models.Model):
    asset_code = models.CharField(unique=True, max_length=100, blank=True, null=True)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    asset_desc = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    part_number = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    warranty_expiry_date = models.DateField(null=True, blank=True)
    remark = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to=content_file_assets, blank=True)

    def __str__(self):
        return self.asset_desc
    class Meta:
        db_table = "tb_assets_inventory"
        ordering = ['-asset_desc']

class Hardware(models.Model):
    hardware_code = models.CharField(max_length=100, blank=True, null=True, unique=True)
    hardware_desc = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)
    licensing_date = models.DateField(null=True, blank=True)
    stock_qty = models.IntegerField(default=0)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to=content_file_hardware, blank=True)

    def __str__(self):
        return self.hardware_desc
    class Meta:
        db_table = "tb_hardware_inventory"
        ordering = ['-hardware_desc']

class CustomerHardware(models.Model):
    hardware_desc = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)
    licensing_date = models.DateField(null=True, blank=True)
    stock_qty = models.IntegerField(default=0)
    customer_name = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)
    proj_name = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.hardware_desc
    class Meta:
        db_table = "tb_customer_hardware"
        ordering = ['-hardware_desc']

class Stationary(models.Model):
    stationary_code = models.CharField(max_length=100, blank=True, null=True, unique=True)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    stationary_desc = models.CharField(max_length=100, blank=True, null=True)
    part_number = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    replenish_qty = models.IntegerField(default=0)
    restock_qty = models.IntegerField(default=0)
    stock_qty = models.IntegerField(default=0)
    photo = models.ImageField(upload_to=content_file_stationary, blank=True)

    def __str__(self):
        return self.stationary_desc
    class Meta:
        db_table = "tb_stationary_inventory"
        ordering = ['-stationary_desc']

class PPE(models.Model):
    ppe_code = models.CharField(max_length=100, blank=True, null=True, unique=True)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    ppe_desc = models.CharField(max_length=100, blank=True, null=True)
    part_number = models.CharField(max_length=100, blank=True, null=True)
    variant = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    replenish_qty = models.IntegerField(default=0)
    restock_qty = models.IntegerField(default=0)
    stock_qty = models.IntegerField(default=0)
    photo = models.ImageField(upload_to=content_file_ppe, blank=True)

    def __str__(self):
        return self.ppe_desc
    class Meta:
        db_table = "tb_ppe_inventory"
        ordering = ['-ppe_desc']

