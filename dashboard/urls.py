from django.conf.urls import url
from dashboard import views

urlpatterns = [
                url(r'^$', views.Dashboard.as_view(), name='dashboard'),
                url(r'^message/', views.message, name='message'),
              ]