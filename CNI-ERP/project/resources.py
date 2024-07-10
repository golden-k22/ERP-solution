from import_export import fields, resources
from project.models import OT, Bom, DoItem, Project, SrItem, Team

class TeamResource(resources.ModelResource):
    class Meta:
        model = Team
        fields = ('emp_no', 'first_name', 'last_name', 'role', 'priority')
        export_order = ('emp_no', 'first_name', 'last_name', 'role', 'priority')

class BomResource(resources.ModelResource):
    class Meta:
        model = Bom
        fields = ('item_id', 'description', 'uom', 'ordered_qty', 'brand', 'delivered_qty', 'delivered_po_no', 'date', 'remark')
        export_order = ('item_id', 'description', 'uom', 'ordered_qty', 'brand', 'delivered_qty', 'delivered_po_no', 'date', 'remark')

class DoItemResource(resources.ModelResource):
    class Meta:
        model = DoItem
        fields = ('description', 'qty', 'uom')
        export_order = ('description', 'qty', 'uom')

class SrItemResource(resources.ModelResource):
    class Meta:
        model = SrItem
        fields = ('description', 'qty', 'uom')
        export_order = ('description', 'qty', 'uom')


class ProjectResource(resources.ModelResource):
    class Meta:
        model = Project
        fields = ('proj_id', 'company_name', 'proj_name', 'start_date', 'end_date', 'proj_incharge', 'proj_status')
        export_order = ('proj_id', 'company_name', 'proj_name', 'start_date', 'end_date', 'proj_incharge', 'proj_status')

class ProjectOtResource(resources.ModelResource):
    class Meta:
        model = OT
        fields = ('proj_id', 'date', 'approved_hour', 'approved_by', 'proj_name')
        export_order = ('proj_id', 'date', 'approved_hour', 'approved_by', 'proj_name')
