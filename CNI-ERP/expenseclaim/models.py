from django.db import models
from datetime import date

from accounts.models import User

def content_file_receipt(instance, filename):
    current_year = date.today().year
    return 'expensesclaim/%s/%s/%s' % (instance.emp_id.emp_id,current_year, filename)
    
# Create your models here.
class ExpensesClaim(models.Model):
    ec_id = models.CharField(max_length=100, blank=True, null=True)
    emp_id = models.CharField(max_length=100, blank=True, null=True)
    total = models.FloatField(blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    submission_date = models.DateField(null=True, blank=True)
    expenses_name = models.CharField(max_length=100, blank=True, null=True)
    approveby = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    verifiedby = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True,related_name='verified_by')

    class Meta:
        db_table = "tb_expenses_claim"

class ExpensesClaimDetail(models.Model):
    ec_id = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(null=True, blank=True)
    proj_id = models.CharField(max_length=100, blank=True, null=True)
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    vendor = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)
    subtotal = models.FloatField(blank=True, null=True)
    gst = models.BooleanField(default=False)
    total = models.FloatField(blank=True, null=True)
    expensesclaim = models.ForeignKey('ExpensesClaim', on_delete=models.SET_NULL, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "tb_expenses_claim_details"

class InvoiceSummary(models.Model):
    date = models.DateField(null=True, blank=True)
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    vendor = models.CharField(max_length=100, blank=True, null=True)
    gstamount = models.FloatField(blank=True, null=True, default=0.0)
    total = models.FloatField(blank=True, null=True)
    expensesclaim = models.ForeignKey('ExpensesClaim', on_delete=models.SET_NULL, blank=True, null=True)
    class Meta:
        db_table = "tb_expenses_invoice_summary"

class InvoiceDetail(models.Model):
    proj_id = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    qty = models.FloatField(blank=True, null=True)
    unit_price = models.FloatField(blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)
    subtotal = models.FloatField(blank=True, null=True)
    gst = models.BooleanField(default=False)
    total = models.FloatField(blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    # expensesclaim = models.ForeignKey('ExpensesClaim', on_delete=models.SET_NULL, blank=True, null=True)
    invoicesummary = models.ForeignKey('InvoiceSummary', on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        db_table = "tb_expenses_invoice_details"

class ExpensesClaimRecipt(models.Model):
    emp_id = models.ForeignKey(ExpensesClaim, on_delete=models.SET_NULL, blank=True, null=True)
    receipt_no = models.CharField(max_length=100,blank=True, null=True)
    receipt_file = models.FileField(upload_to=content_file_receipt, blank=True)
    receipt_name = models.CharField(max_length=100, blank=True, null=True)
    upload_by = models.CharField(max_length=100, blank=True, null=True)
    class Meta:
        db_table = "tb_expenses_claim_receipt"



