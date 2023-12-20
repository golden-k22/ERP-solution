from django.conf.urls import url
from siteprogress import views

urlpatterns = [
    url(r'^siteprogress/$', views.SiteProgressView.as_view(), name='siteprogress'),
    url(r'^ajax_plog_items/$', views.ajax_plog_items, name='ajax_plog_items'),
    url(r'^ajax_planning_items/$', views.ajax_planning_items, name='ajax_planning_items'),
    url(r'^ajax_all_overview/$', views.overViewList, name='ajax_all_overview'),
    url(r'^ajax_all_planning_overview/$', views.planningOverViewList, name='ajax_all_planning_overview'),
    url(r'^ajax_filter_overview/$', views.overViewFilterList, name='ajax_filter_overview'),
    url(r'^ajax_filter_planning_overview/$', views.planningOverViewFilterList, name='ajax_filter_planning_overview'),
    url(r'^ajax_all_progresslog/$', views.progressLogList, name='ajax_all_progresslog'),
    url(r'^ajax_add_progress/$', views.progressadd, name='ajax_add_progress'),
    url(r'^ajax_add_planning/$', views.planningadd, name='ajax_add_planning'),
    url(r'^ajax_get_activity/$', views.ajax_get_activity, name='ajax_get_activity'),
    url(r'^ajax_get_site_uom_name/$', views.ajax_get_uom_name, name='ajax_get_site_uom_name'),
    url(r'^ajax_filter_progresslog/$', views.progressLogFilterList, name='ajax_filter_progresslog'),
    url(r'^ajax_delete_progresslog/$', views.ajax_delete_progresslog, name='ajax_delete_progresslog'),
    url(r'^ajax_delete_planning/$', views.ajax_delete_planning, name='ajax_delete_planning'),
    url(r'^ajax_get_progresslog/$', views.ajax_get_progresslog, name='ajax_get_progresslog'),
    url(r'^ajax_get_planning/$', views.ajax_get_planning, name='ajax_get_planning'),
    url(r'^ajax_submit_planning/$', views.ajax_submit_planning, name='ajax_submit_planning'),
    url(r'^ajax_repeat_planning/$', views.ajax_repeat_planning, name='ajax_repeat_planning'),
    url(r'^ajax_is_repeated/$', views.ajax_is_repeated, name='ajax_is_repeated'),
]