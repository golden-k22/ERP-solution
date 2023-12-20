from import_export import fields, resources

from maintenance.models import MainSrItem, Maintenance


class MainSrItemResource(resources.ModelResource):
    class Meta:
        model = MainSrItem
        fields = ('description', 'qty', 'uom')
        export_order = ('description', 'qty', 'uom')

class MaintenanceResource(resources.ModelResource):
    class Meta:
        model = Maintenance
        fields = ('main_no', 'customer', 'start_date', 'end_date', 'in_incharge', 'main_status')
        export_order = ('main_no', 'customer', 'start_date', 'end_date', 'in_incharge', 'main_status')