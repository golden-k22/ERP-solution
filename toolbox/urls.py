from django.conf.urls import url
from toolbox import views

urlpatterns = [
    url(r'^toolbox/$', views.ToolBoxList.as_view(), name='all_toolbox'),
    url(r'^ajax_all_tbm/$', views.ajax_tbms, name='ajax_all_tbm'),
    url(r'^ajax_delete_tbm/$', views.tbmdelete, name='ajax_delete_tbm'),
    url(r'^ajax_delete_tbm_attend/$', views.tbmattenddelete, name='ajax_delete_tbm_attend'),
    url(r'^ajax_add_toolbox/$', views.toolboxadd, name='ajax_add_toolbox'),
    url(r'^ajax_get_toolbox/$', views.getToolBox, name='ajax_get_toolbox'),
    url(r'^ajax_get_toolbox_attend/$', views.getToolBoxAttend, name='ajax_get_toolbox_attend'),
    url(r'^ajax_filter_toolbox/$', views.ajax_toolbox_filter, name='ajax_filter_toolbox'),
    url(r'^toolbox-detail/(?P<pk>[0-9]+)/$', views.ToolBoxDetailView.as_view(), name='toolbox_detail'),
    url(r'^ajax_update_toolbox/$', views.UpdateToolbox, name='ajax_update_toolbox'),
    url(r'^ajax_check_tbmnumber/$', views.check_tbm_number, name='ajax_check_tbmnumber'),
    url(r'^ajax_add_toolbox_attend/$', views.toolboxattendadd, name='ajax_add_toolbox_attend'),
    url(r'^ajax_filter_tbm/$', views.ajax_tbmFilterList, name='ajax_filter_tbm'),
    url(r'^export_tbm_pdf/(?P<value>\w+)/$', views.exportTbmPDF, name='export_tbm_pdf'),
    url(r'^ajax_add_toolboxlog_item/$', views.toolboxlogitemadd, name='ajax_add_toolboxlog_item'),
    url(r'^ajax_get_toolboxlog_item/$', views.getToolBoxLogItem, name='ajax_get_toolboxlog_item'),
    url(r'^ajax_delete_tbmlog_item/$', views.tbmilogtemdelete, name='ajax_delete_tbmlog_item'),
    url(r'^ajax_get_user_nric/$', views.ajax_get_user_nric, name='ajax_get_user_nric'),
]