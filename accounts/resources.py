from import_export import fields, resources

from accounts.models import WorkLog

class WorkLogResource(resources.ModelResource):
    class Meta:
        model = WorkLog
        fields = ('emp_no', 'project_name', 'projectcode', 'checkin_time', 'checkin_lat', 'checkin_lng', 'checkout_time', 'checkout_lat', 'checkout_lng')
        export_order = ('emp_no', 'project_name', 'projectcode', 'checkin_time', 'checkin_lat', 'checkin_lng', 'checkout_time', 'checkout_lat', 'checkout_lng')

