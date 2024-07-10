from import_export import fields, resources

from inventory.models import Material, Asset, PPE, Hardware, Stationary

class MaterialResource(resources.ModelResource):
    class Meta:
        model = Material
        fields = ('material_code', 'product_desc', 'supplier_name', 'part_number', 'color', 'brand', 'location', 'uom','remark', 'replenish_qty', 'restock_qty', 'stock_qty')
        export_order = ('material_code', 'product_desc', 'supplier_name', 'part_number', 'color', 'brand', 'location', 'uom','remark', 'replenish_qty', 'restock_qty', 'stock_qty')

class AssetResource(resources.ModelResource):
    class Meta:
        model = Asset
        fields = ('asset_code', 'supplier_name', 'asset_desc', 'category', 'part_number', 'brand', 'status', 'type', 'remark')
        export_order = ('asset_code', 'supplier_name', 'asset_desc', 'category', 'part_number', 'brand', 'status', 'type', 'remark')

class PPEResource(resources.ModelResource):
    class Meta:
        model = PPE
        fields = ('ppe_code', 'supplier_name', 'ppe_desc', 'part_number', 'variant', 'brand', 'status', 'uom', 'replenish_qty', 'restock_qty', 'stock_qty')
        export_order = ('ppe_code', 'supplier_name', 'ppe_desc', 'part_number', 'variant', 'brand', 'status', 'uom', 'replenish_qty', 'restock_qty', 'stock_qty')

class HardWareResource(resources.ModelResource):
    class Meta:
        model = Hardware
        fields = ('hardware_code','supplier_name','hardware_desc', 'serial_number', 'brand', 'uom','expiry_date','licensing_date', 'stock_qty', 'remark')
        export_order = ('hardware_code','supplier_name','hardware_desc', 'serial_number', 'brand', 'uom','expiry_date','licensing_date', 'stock_qty', 'remark')

class CustomerHardWareResource(resources.ModelResource):
    class Meta:
        model = Hardware
        fields = ('hardware_code','customer_name','proj_name','hardware_desc', 'serial_number', 'brand', 'uom','expiry_date','licensing_date', 'stock_qty', 'remark', 'status')
        export_order = ('hardware_code','customer_name','proj_name','hardware_desc', 'serial_number', 'brand', 'uom','expiry_date','licensing_date', 'stock_qty', 'remark', 'status')

class StationaryResource(resources.ModelResource):
    class Meta:
        model = Stationary
        fields = ('stationary_code','supplier_name','stationary_desc', 'part_number','variant', 'brand', 'status', 'uom', 'replenish_qty', 'restock_qty', 'stock_qty')
        export_order = ('stationary_code','supplier_name','stationary_desc', 'part_number','variant', 'brand', 'status', 'uom', 'replenish_qty', 'restock_qty', 'stock_qty')