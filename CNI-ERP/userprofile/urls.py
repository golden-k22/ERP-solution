from django.conf.urls import url
from accounts.models import User
from userprofile import views

urlpatterns = [
    url(r'^change-password/$', views.change_password, name='change_password'),
    url(r'^ajax_check_change/$', views.check_password, name='ajax_check_change'),
    url(r'^about/$', views.AboutView.as_view(), name='about'),
]
