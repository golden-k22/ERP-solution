from django.conf.urls import url
from django.urls import path

from . import views


urlpatterns = [
    path("calender/", views.CalendarViewNew.as_view(), name="calendar"),
    path("event/new/", views.create_event, name="event_new"),
    path("all-event-list/", views.AllEventsListView.as_view(), name="all_events"),
    path(
        "running-event-list/",
        views.RunningEventsListView.as_view(),
        name="running_events",
    ),
    url(r'^event-list/$', views.EventList.as_view(), name='event_list'),
    url(r'^ajax_all_events/$', views.ajax_all_events, name='ajax_all_events'),
    url(r'^ajax_get_event/$', views.ajax_get_event, name='ajax_get_event'),
    url(r'^ajax_delete_event/$', views.ajax_delete_event, name='ajax_delete_event'),
    url(r'^ajax_add_event/$', views.ajax_add_event, name='ajax_add_event'),
    url(r'^ajax_filter_events/$', views.ajax_filter_events, name='ajax_filter_events'),
]
