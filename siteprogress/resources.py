from import_export import fields, resources
from siteprogress.models import SiteProgress

class SiteProgressResource(resources.ModelResource):
    class Meta:
        model = SiteProgress
        fields = ('description', 'qty', 'uom', 'date', 'remark')
        export_order = ('description', 'qty', 'uom', 'date', 'remark')