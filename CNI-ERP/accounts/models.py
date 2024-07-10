from cities_light.models import Country
from django.contrib.auth.models import AbstractUser
from django.db import models


class Uom(models.Model):
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "tb_uom"


def content_file_signature(instance, filename):
    return 'user/signature/{1}'.format(instance, filename)


# Create your models here.
class Role(models.Model):
    name = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "tb_role"


class User(AbstractUser):
    empid = models.CharField(max_length=20, blank=True, null=True)
    nric = models.CharField(max_length=250, blank=True, null=True)
    nationality = models.CharField(max_length=250, blank=True, null=True)
    wp_type = models.CharField(max_length=50, blank=True, null=True)
    wp_no = models.CharField(max_length=50, blank=True, null=True)
    wp_expiry = models.DateField(null=True, blank=True)
    passport_no = models.CharField(max_length=50, blank=True, null=True)
    passport_expiry = models.DateField(null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    role = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=250, blank=True, null=True)
    latitude = models.CharField(max_length=50, blank=True, null=True)
    longitude = models.CharField(max_length=50, blank=True, null=True)
    pincode = models.CharField(max_length=150, blank=True, null=True)
    fcm_token = models.CharField(max_length=500, blank=True, null=True)
    basic_salary = models.CharField(max_length=50, blank=True, null=True)
    password_box = models.CharField(max_length=200, blank=True, null=True)
    signature = models.ImageField(upload_to=content_file_signature, blank=True)

    def __str__(self):
        return self.username

    class Meta:
        db_table = "tb_user"


class UserAddress(models.Model):
    emp_id = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    address = models.CharField(max_length=250, blank=True, null=True)
    unit = models.CharField(max_length=250, blank=True, null=True)
    postal_code = models.IntegerField(default=0)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.address

    class Meta:
        db_table = "tb_user_address"


class WorkLog(models.Model):
    Shift_Dict = (
        ('Day', 'Day'),
        ('Night', 'Night'),
    )
    Checkin_transport_Dict = (
        ('Public', 'Public'),
        ('Company', 'Company'),
    )
    Checkout_transport_Dict = (
        ('Public', 'Public'),
        ('Company', 'Company'),
    )
    emp_no = models.CharField(max_length=250, blank=True, null=True)
    project_name = models.CharField(max_length=250, blank=True, null=True)
    projectcode = models.CharField(max_length=250, blank=True, null=True)
    checkin_time = models.DateTimeField(auto_now_add=False, blank=True, null=True)
    worker_id = models.CharField(max_length=250, blank=True, null=True)
    checkin_comments = models.CharField(max_length=250, blank=True, null=True)
    checkin_address = models.CharField(max_length=250, blank=True, null=True)
    checkin_lat = models.CharField(max_length=250, blank=True, null=True)
    checkin_lng = models.CharField(max_length=250, blank=True, null=True)
    checkout_time = models.DateTimeField(auto_now_add=False, blank=True, null=True)
    checkout_worker_id = models.CharField(max_length=250, blank=True, null=True)
    checkout_address = models.CharField(max_length=250, blank=True, null=True)
    checkout_lat = models.CharField(max_length=250, blank=True, null=True)
    checkout_lng = models.CharField(max_length=250, blank=True, null=True)
    checkout_comments = models.CharField(max_length=250, blank=True, null=True)

    shift_type = models.CharField(max_length=250, choices=Shift_Dict, default='Day',null=True)
    checkin_transport=models.CharField(max_length=250, choices=Checkin_transport_Dict, default='Public',null=True)
    checkout_transport=models.CharField(max_length=250, choices=Checkout_transport_Dict, default='Public',null=True)
    def __str__(self):
        return self.project_name

    class Meta:
        db_table = "tb_worklog"
        verbose_name_plural = "tb_worklog"


class MaterialLog(models.Model):
    emp_no = models.CharField(max_length=250, blank=True, null=True)
    material_code = models.CharField(max_length=250, blank=True, null=True)
    product_desc = models.CharField(max_length=250, blank=True, null=True)
    project_name = models.CharField(max_length=250, blank=True, null=True)
    material_out = models.CharField(max_length=250, blank=True, null=True)
    date_time = models.DateTimeField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.material_code

    class Meta:
        db_table = "tb_materialout"

class PPELog(models.Model):
    emp_no = models.CharField(max_length=250, blank=True, null=True)
    ppe_code = models.CharField(max_length=250, blank=True, null=True)
    ppe_desc = models.CharField(max_length=250, blank=True, null=True)
    project_name = models.CharField(max_length=250, blank=True, null=True)
    ppe_out = models.CharField(max_length=250, blank=True, null=True)
    date_time = models.DateTimeField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.ppe_code

    class Meta:
        db_table = "tb_ppeout"

class StationaryLog(models.Model):
    emp_no = models.CharField(max_length=250, blank=True, null=True)
    stationary_code = models.CharField(max_length=250, blank=True, null=True)
    stationary_desc = models.CharField(max_length=250, blank=True, null=True)
    project_name = models.CharField(max_length=250, blank=True, null=True)
    stationary_out = models.CharField(max_length=250, blank=True, null=True)
    date_time = models.DateTimeField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.stationary_code

    class Meta:
        db_table = "tb_stationaryout"


class AssetLog(models.Model):
    emp_no = models.CharField(max_length=250, blank=True, null=True)
    asset_code = models.CharField(max_length=250, blank=True, null=True)
    asset_name = models.CharField(max_length=250, blank=True, null=True)
    check_status = models.CharField(max_length=250, blank=True, null=True)

    checkin_date = models.DateTimeField(blank=True, null=True)
    checkout_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.asset_code

    class Meta:
        db_table = "tb_assetlog"


class OTCalculation(models.Model):

    Shift_Dict = (
        ('Day', 'Day'),
        ('Night', 'Night'),
    )
    Checkin_transport_Dict = (
        ('Public', 'Public'),
        ('Company', 'Company'),
    )
    Checkout_transport_Dict = (
        ('Public', 'Public'),
        ('Company', 'Company'),
    )
    emp_no = models.CharField(max_length=250, blank=True, null=True)
    project_no = models.CharField(max_length=250, blank=True, null=True)
    time_in = models.DateTimeField(blank=True, null=True)
    time_out = models.DateTimeField(blank=True, null=True)
    approved_ot_hr = models.IntegerField(default=0)
    firsthr = models.CharField(max_length=250, blank=True, null=True)
    secondhr = models.CharField(max_length=250, blank=True, null=True)
    meal_allowance = models.CharField(max_length=250, blank=True, null=True)
    ph = models.IntegerField(default=0)

    shift_type = models.CharField(max_length=250, choices=Shift_Dict, default='Day',null=True)
    checkin_transport=models.CharField(max_length=250, choices=Checkin_transport_Dict, default='Public',null=True)
    checkout_transport=models.CharField(max_length=250, choices=Checkout_transport_Dict, default='Public',null=True)
    late_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    night_allowance = models.IntegerField(default=0)
    def __str__(self):
        return self.emp_no

    class Meta:
        db_table = "tb_ot_calculation"


class Privilege(models.Model):
    sales_summary = models.CharField(max_length=250, blank=True, null=True)
    sales_report = models.CharField(max_length=250, blank=True, null=True)
    proj_summary = models.CharField(max_length=250, blank=True, null=True)
    proj_ot = models.CharField(max_length=250, blank=True, null=True)
    invent_material = models.CharField(max_length=250, blank=True, null=True)
    prof_summary = models.CharField(max_length=250, blank=True, null=True)
    quotation = models.CharField(max_length=250, blank=True, null=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        db_table = "tb_privilege"


class UserCert(models.Model):
    emp_id = models.CharField(max_length=250, blank=True, null=True)
    course = models.CharField(max_length=250, blank=True, null=True)
    course_no = models.CharField(max_length=250, blank=True, null=True)
    school = models.CharField(max_length=250, blank=True, null=True)
    course_expiry = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "tb_user_cert"


class UserItemTool(models.Model):
    emp_id = models.CharField(max_length=250, blank=True, null=True)
    category = models.CharField(max_length=250, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    qty = models.IntegerField(default=0)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    issue_date = models.DateField(null=True, blank=True)
    issued_by = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "tb_user_item_tool"


class UserItemIssued(models.Model):
    empid = models.CharField(max_length=250, blank=True, null=True)
    category = models.CharField(max_length=250, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    qty = models.IntegerField(default=0)
    uom = models.ForeignKey(Uom, on_delete=models.SET_NULL, blank=True, null=True)
    issue_date = models.DateField(null=True, blank=True)
    issued_by = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "tb_user_item_issued"


class Holiday(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "tb_holiday"


class NotificationPrivilege(models.Model):
    maintenance_reminded = models.BooleanField(blank=True, null=True, default=True)
    project_no_created = models.BooleanField(blank=True, null=True, default=True)
    project_status = models.BooleanField(blank=True, null=True, default=True)
    project_end = models.IntegerField(default=2)
    tbm_no_created = models.BooleanField(blank=True, null=True, default=True)
    reminder_signature = models.IntegerField(default=3)
    reminder_invoice = models.IntegerField(default=3)
    inventory_item_deleted = models.BooleanField(blank=True, null=True, default=True)
    stock_equal_restock = models.BooleanField(blank=True, null=True, default=True)
    do_status = models.BooleanField(blank=True, null=True, default=True)
    service_status = models.BooleanField(blank=True, null=True, default=True)
    pc_status = models.BooleanField(blank=True, null=True, default=True)
    usergroup_created = models.BooleanField(blank=True, null=True, default=True)
    user_no_created = models.BooleanField(blank=True, null=True, default=True)
    claim_submitted = models.BooleanField(blank=True, null=True, default=True)
    contract_end = models.IntegerField(default=3)
    hardware_end = models.IntegerField(default=3)
    schedule_end = models.IntegerField(default=2)
    password_change = models.BooleanField(blank=True, null=True, default=True)
    is_email = models.BooleanField(blank=True, null=True, default=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        db_table = "tb_privilege_notification"
