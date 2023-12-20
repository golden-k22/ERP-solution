from django.conf.urls import url
from inventory import views

urlpatterns = [
    #material 
    url(r'^inventory-materials/$', views.InventoryMaterialView.as_view(), name='all_inventory_materials'),
    url(r'^ajax_delete_material/$', views.materialdelete, name='ajax_delete_material'),
    url(r'^ajax_add_material/$', views.materialinventoryadd, name='ajax_add_material'),
    url(r'^ajax_get_material/$', views.getMaterial, name='ajax_get_material'),
    url(r'^ajax_all_inventory/$', views.ajax_inventory, name='ajax_all_inventory'),
    url(r'^ajax_filter_inventory/$', views.ajax_filter_inventory, name='ajax_filter_inventory'),
    url(r'^ajax-export-materials/$', views.ajax_export_materials, name='ajax-export-materials'),
    url(r'^ajax-import-materials/$', views.ajax_import_materials, name='ajax-import-materials'),
    url(r'^ajax_check_material_code/$', views.check_material_code, name='ajax_check_material_code'),

    #inventory Asset
    url(r'^inventory-assets/$', views.InventoryAssetView.as_view(), name='all_inventory_assets'),
    url(r'^ajax_delete_asset/$', views.assetdelete, name='ajax_delete_asset'),
    url(r'^ajax_add_asset/$', views.assetinventoryadd, name='ajax_add_asset'),
    url(r'^ajax_get_asset/$', views.getAsset, name='ajax_get_asset'),
    url(r'^ajax_all_asset/$', views.ajax_asset, name='ajax_all_asset'),
    url(r'^ajax_filter_asset/$', views.ajax_filter_asset, name='ajax_filter_asset'),
    url(r'^ajax-export-assets/$', views.ajax_export_assets, name='ajax-export-assets'),
    url(r'^ajax-import-assets/$', views.ajax_import_assets, name='ajax-import-assets'),

    #ppe part
    url(r'^inventory-ppe/$', views.InventoryPPEView.as_view(), name='all_inventory_ppes'),
    url(r'^ajax_delete_ppe/$', views.ppedelete, name='ajax_delete_ppe'),
    url(r'^ajax_add_ppe/$', views.ppeinventoryadd, name='ajax_add_ppe'),
    url(r'^ajax_get_ppe/$', views.getPPE, name='ajax_get_ppe'),
    url(r'^ajax_all_ppe/$', views.ajax_ppe, name='ajax_all_ppe'),
    url(r'^ajax_filter_ppe/$', views.ajax_filter_ppe, name='ajax_filter_ppe'),
    url(r'^ajax-export-ppes/$', views.ajax_export_ppes, name='ajax-export-ppes'),
    url(r'^ajax-import-ppe/$', views.ajax_import_ppe, name='ajax-import-ppe'),

    #stationary part
    url(r'^inventory-stationary/$', views.InventoryStationaryView.as_view(), name='all_inventory_stationarys'),
    url(r'^ajax_delete_stationary/$', views.stationarydelete, name='ajax_delete_stationary'),
    url(r'^ajax_add_stationary/$', views.stationaryinventoryadd, name='ajax_add_stationary'),
    url(r'^ajax_get_stationary/$', views.getStationary, name='ajax_get_stationary'),
    url(r'^ajax_all_stationary/$', views.ajax_stationary, name='ajax_all_stationary'),
    url(r'^ajax_filter_stationary/$', views.ajax_filter_stationary, name='ajax_filter_stationary'),
    url(r'^ajax-export-stationary/$', views.ajax_export_stationary, name='ajax-export-stationary'),
    url(r'^ajax-import-stationary/$', views.ajax_import_stationary, name='ajax-import-stationary'),
    url(r'^ajax_check_stationary_code/$', views.check_stationary_code, name='ajax_check_stationary_code'),

    #hardware part
    url(r'^inventory-hardware/$', views.InventoryHardwareView.as_view(), name='all_inventory_hardwares'),
    url(r'^ajax_delete_hardware/$', views.hardwaredelete, name='ajax_delete_hardware'),
    url(r'^ajax_add_hardware/$', views.hardwareinventoryadd, name='ajax_add_hardware'),
    url(r'^ajax_get_hardware/$', views.getHardware, name='ajax_get_hardware'),
    url(r'^ajax_check_hdnumber/$', views.checkHardwareNo, name='ajax_check_hdnumber'),
    url(r'^ajax_all_hardware/$', views.ajax_hardware, name='ajax_all_hardware'),
    url(r'^ajax_filter_hardware/$', views.ajax_filter_hardware, name='ajax_filter_hardware'),
    url(r'^ajax-export-hardwares/$', views.ajax_export_hardwares, name='ajax-export-hardwares'),
    url(r'^ajax-import-hardwares/$', views.ajax_import_hardwares, name='ajax-import-hardwares'),
    #Customer's hardware part
    url(r'^customer-hardware/$', views.CustomerHardwareView.as_view(), name='customer-hardware'),
    url(r'^ajax_delete_customer_hardware/$', views.customer_hardware_delete, name='ajax_delete_customer_hardware'),
    url(r'^ajax_add_customer_hardware/$', views.customer_hardware_add, name='ajax_add_customer_hardware'),
    url(r'^ajax_get_customer_hardware/$', views.getCustomerHardware, name='ajax_get_customer_hardware'),
    url(r'^ajax_all_customer_hardware/$', views.ajax_customer_hardware, name='ajax_all_customer_hardware'),
    url(r'^ajax_filter_customer_hardware/$', views.ajax_filter_customer_hardware, name='ajax_filter_customer_hardware'),
    url(r'^ajax-export-customer-hardwares/$', views.ajax_export_customer_hardwares, name='ajax-export-customer-hardwares'),
    url(r'^ajax-import-customer-hardwares/$', views.ajax_import_customer_hardwares, name='ajax-import-customer-hardwares'),
    url(r'^ajax_hardware_items/$', views.ajax_hardware_items, name='ajax_hardware_items'),
    url(r'^ajax_customer_hardware_clone/$', views.customer_hardware_clone, name='ajax_customer_hardware_clone'),
]
