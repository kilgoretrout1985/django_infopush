# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

import string
import random
from unittest import skipUnless
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.utils import translation, timezone
from django.utils.six import StringIO
from django.contrib.sites.models import Site
#from django.contrib.auth import get_user_model
from django.core.management import call_command

from .settings import GCM_URL, FCM_SENDER_ID
from .models import DigestSubscription, Task


def __fake_letters(length=10):
    letters = string.ascii_letters + string.digits
    letters_len = len(letters)
    s = []
    for i in range(length):
        s.append(letters[ random.randint(0, letters_len-1) ])
    return ''.join(s)


def _new_subscription_obj_for_test(is_active=True):
    s = DigestSubscription()
    s.endpoint = 'https://updates.push.services.mozilla.com/wpush/v1/' + __fake_letters(30)
    s.timezone = settings.TIME_ZONE
    s.is_active = is_active
    if is_active:
        s.activated_at = timezone.now()
    s.save()
    return s


def _new_task_obj_for_test(is_active=True, run_at=None, started_at=None, done_at=None):
    t = Task()
    t.title = __fake_letters(10)
    t.message = __fake_letters(50)
    t.url = 'https://' + Site.objects.all()[0].domain + reverse('push_info_disable')
    t.is_active = is_active
    if run_at is not None:
        t.run_at = run_at
    t.save()
    t.started_at = started_at
    t.done_at = done_at
    # fake task as done
    if is_active and started_at is not None and done_at is not None:
        for tz_layout in t.timezonelayout_set.all():
            tz_layout.started_at = started_at
            tz_layout.done_at = done_at
            tz_layout.save()
    t.save()
    return t


class PushTests(TestCase):
    def test_push_on_off_view_working(self):
        response = self.client.get(reverse('push_on_off'))
        self.assertContains(response, 'js-push-button')

    def test_push_info_disable_view_working(self):
        with translation.override('en'):
            response = self.client.get(reverse('push_info_disable'))
        # 3 major content sections
        self.assertContains(response, 'Chrome')
        self.assertContains(response, 'Firefox')
        self.assertContains(response, 'Chrome for Android')
    
    @skipUnless(FCM_SENDER_ID, "This test is needed only for FCM project setup, not for default VAPID.")
    def test_manifest_json_has_fcm_sender_id(self):
        response = self.client.get(reverse('push_manifest_json'))
        self.assertTrue( response.json()['gcm_sender_id'] == FCM_SENDER_ID )
    
    def test_view_saves_subscription_on_server(self):
        response = self.client.post(reverse('push_save'), {
            'endpoint': GCM_URL + '/hstwtdjsyTDSDGSU',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue( int(response.json()['response']['id']) > 0 )
    
    def test_view_deactivates_subscription_on_server(self):
        obj = _new_subscription_obj_for_test(True)
        response = self.client.post(reverse('push_deactivate'), {
            'endpoint': obj.endpoint,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.json()['response']['id']), obj.pk)
        obj.refresh_from_db()
        self.assertFalse(obj.is_active)
    
    @skipUnless(settings.SITE_ID, "Can't generate push-task obj without sites framework.")
    def test_last_notification_view(self):
        obj = _new_task_obj_for_test(True,
                                     timezone.now()-timedelta(days=3),
                                     timezone.now(), timezone.now())
        response = self.client.get(reverse('push_last_notification'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(obj.title, response.json()['notification']['title'])
        self.assertEqual(obj.message, response.json()['notification']['message'])
        self.assertTrue('url' in response.json()['notification'] and response.json()['notification']['url'])
        # last notification increases views counter for task
        obj.refresh_from_db()
        self.assertEqual(obj.views, 1)

    @skipUnless(settings.SITE_ID, "Can't generate push-task obj without sites framework.")
    def test_show_notification_view(self):
        obj = _new_task_obj_for_test(True,
                             timezone.now()-timedelta(days=3),
                             timezone.now(), timezone.now())
        response = self.client.get(reverse('push_show_notification', args=[obj.id,]))
        self.assertRedirects(response, obj.url+'?from=push')
        # show notification increases clicks counter
        obj.refresh_from_db()
        self.assertEqual(obj.clicks, 1)
    
    @skipUnless(settings.SITE_ID, "Can't generate push-task obj without sites framework.")
    def test_pushsend_management_command(self):
        subscr = _new_subscription_obj_for_test(True)
        task = _new_task_obj_for_test(True, timezone.now()-timedelta(days=3))
        out = StringIO()
        call_command('pushsend', stdout=out)
        subscr.refresh_from_db()
        # fake endpoint will have to give this subscription some error points
        self.assertTrue(subscr.errors > 0 or not subscr.is_active)
        task.refresh_from_db()
        self.assertTrue(task.done_at is not None)
        self.assertTrue(task.started_at is not None)
    
    # @skipUnless(settings.SITE_ID, "Can't generate push-task obj without sites framework.")
    # def test_task_admin_form(self):
    #     # enter /admin (superuser so we don't have to bother with permissions)
    #     user = get_user_model().objects.create_superuser(
    #         'username', 'admin@localhost', 'password123'
    #     )
    #     self.client.force_login(user)
    #     response = self.client.post(
    #         reverse('admin:push_task_add'), 
    #         {
    #             'title': 'push title',
    #             'message': 'push message',
    #             'url': '/',
    #             'run_at': timezone.now(),
    #         }
    #     )
    #     self.assertEqual(response.status_code, 200)
    #     # total 1 task should be in test DB now
    #     self.assertEqual(Task.objects.count(), 1)
    #     self.client.logout()
