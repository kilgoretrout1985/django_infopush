# -*- coding: utf-8 -*-

from django.urls import re_path
from . import views


urlpatterns = [
    # subscriptions
    re_path(r'^on[\-\_]off/$', views.on_off, name='push_on_off'),
    re_path(r'^info[\-\_]disable/$', views.info_disable, name='push_info_disable'),
    re_path(r'^manifest\.json$', views.manifest_json, name='push_manifest_json'),
    re_path(r'^save/$', views.save, name='push_save'),
    re_path(r'^deactivate/$', views.deactivate, name='push_deactivate'),
    
    # tasks
    re_path(r'^last_notification/$', views.last_notification, name='push_last_notification'),
    re_path(r'^show_notification/(\d+)/$', views.show_notification, name='push_show_notification'),
    re_path(r'^notification_plus_one/(views|closings)/(\d+)/$',
        views.notification_plus_one, name='push_notification_plus_one'),
]
