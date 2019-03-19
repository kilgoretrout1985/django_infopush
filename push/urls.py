# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

from django.conf.urls import url
from . import views


urlpatterns = [
    # subscriptions
    url(r'^on[\-\_]off/$', views.on_off, name='push_on_off'),
    url(r'^info[\-\_]disable/$', views.info_disable, name='push_info_disable'),
    url(r'^manifest\.json$', views.manifest_json, name='push_manifest_json'),
    url(r'^save/$', views.save, name='push_save'),
    url(r'^deactivate/$', views.deactivate, name='push_deactivate'),
    
    # tasks
    url(r'^last_notification/$', views.last_notification, name='push_last_notification'),
    url(r'^show_notification/(\d+)/$', views.show_notification, name='push_show_notification'),
    url(r'^notification_plus_one/(views|closings)/(\d+)/$',
        views.notification_plus_one, name='push_notification_plus_one'),
]
