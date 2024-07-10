from django.conf.urls import url
from maintenance import views

urlpatterns = [
    url(r'^maintenance/$', views.MaintenanceView.as_view(), name='all_maintenance'),
    url(r'^ajax_filter_maintenance/$', views.ajax_filter_maintenance, name='ajax_filter_maintenance'),
    url(r'^add-maintenance/$', views.maintenanceadd, name='ajax_add_maintenance'),
    url(r'^ajax_get_maintenance/$', views.getMaintenanace, name='ajax_get_maintenance'),
    url(r'^ajax_delete_maintenanace/$', views.maintenancedelete, name='ajax_delete_maintenanace'),
    url(r'^maintenance-detail/(?P<pk>[0-9]+)/$', views.MaintenanceDetailView.as_view(), name='maintenance_detail'),
    url(r'^ajax_update_main/$', views.UpdateMain, name='ajax_update_main'),

    url(r'^ajax_add_main_file/$', views.ajax_add_main_file, name='ajax_add_main_file'),
    url(r'^ajax_delete_main_file/$', views.deleteMainFile, name='ajax_delete_main_file'),
    url(r'^ajax_check_main_srnumber/$', views.ajax_check_main_srnumber, name='ajax_check_main_srnumber'),
    url(r'^ajax_add_main_sr/$', views.mainsradd, name='ajax_add_main_sr'),
    url(r'^ajax_add_mainsr_doc/$', views.mainsrdocadd, name='ajax_add_mainsr_doc'),
    url(r'^ajax_delete_mainsr/$', views.deleteMainSR, name='ajax_delete_mainsr'),

    url(r'^maintenance-detail/(?P<pk>[0-9]+)/service-report-detail/(?P<srpk>[0-9]+)/$', views.MainSrDetailView.as_view(), name='maintenance_sr_detail'),
    url(r'^ajax_update_main_service_report/$', views.ajax_update_main_service_report, name='ajax_update_main_service_report'),
    url(r'^ajax_mainsr_item_add/$', views.mainsrItemAdd, name='ajax_mainsr_item_add'),
    url(r'^ajax_get_mainsr_item/$', views.getMainSrItem, name='ajax_get_mainsr_item'),
    url(r'^ajax_delete_main_service_item/$', views.deleteMainSRItem, name='ajax_delete_main_service_item'),

    url(r'^ajax_export_main_sr_item/(?P<maintenanceid>[^/]+)/(?P<srid>[^/]+)/$', views.ajax_export_main_sr_item, name='ajax_export_main_sr_item'),
    url(r'maintenance-detail/(?P<pk>[0-9]+)/service-detail/(?P<srpk>[0-9]+)/signature-create/$', views.MainSrSignatureCreate.as_view(), name='main_sr_signature_create'),
    url(r'maintenance-detail/(?P<pk>[0-9]+)/service-detail/(?P<srpk>[0-9]+)/signature-update/(?P<signpk>[0-9]+)/$', views.MainSrSignatureUpdate.as_view(), name='main_sr_signature_update'),

    url(r'^ajax_add_device/$', views.maindeviceadd, name='ajax_add_device'),
    url(r'^ajax_get_device/$', views.getDevice, name='ajax_get_device'),
    url(r'^ajax_delete_device/$', views.devicedelete, name='ajax_delete_device'),

    url(r'^ajax_add_schedule/$', views.scheduleadd, name='ajax_add_schedule'),
    url(r'^ajax_delete_schedule/$', views.scheduledelete, name='ajax_delete_schedule'),
    url(r'^ajax_get_schedule/$', views.getSchedule, name='ajax_get_schedule'),

    url(r'^export_main_sr_pdf/(?P<value>\w+)/$', views.exportMainSrPDF, name='export_main_sr_pdf'),

    url(r'^ajax-export-maintenance/$', views.ajax_export_maintenance, name='ajax-export-maintenance'),

    url(r'^ajax-import-maintenance/$', views.ajax_import_maintenance, name='ajax-import-maintenance'),
    url(r'^ajax_add_mainsrsignature_sign/$', views.addMainSrSign, name='ajax_add_mainsrsignature_sign'),
    url(r'^ajax_get_mainsrsignature_sign/$', views.getMainSrSign, name='ajax_get_mainsrsignature_sign'),
]