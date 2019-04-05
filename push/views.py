# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

import pytz
from PIL import Image

import logging

from django.db import IntegrityError, connection
from django.http import JsonResponse, Http404, HttpResponse
from django.views.decorators.cache import never_cache, cache_page
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.shortcuts import render, redirect
from django.conf import settings
from django.urls import reverse, NoReverseMatch
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.contrib.staticfiles import finders
from django.contrib.sites.shortcuts import get_current_site

from .settings import FCM_SENDER_ID, GCM_URL, APP_ICON_URLS, USE_CSRF, \
                      APP_BACKGROUND_COLOR, APP_THEME_COLOR
from .models import DigestSubscription, Task, TimezoneLayout


logger = logging.getLogger(__name__)


@never_cache
def on_off(request):
    return render(request, 'push/on_off.html')


def info_disable(request):
    return render(request, 'push/info_disable.html')


@cache_page(86400)
def manifest_json(request):
    # we need this to set up gcm_sender_id
    # https://developers.google.com/web/updates/2014/11/Support-for-installable-web-apps-with-webapp-manifest-in-chrome-38-for-Android
    try:
        start_url = "%s" % reverse('homepage')
    except NoReverseMatch:
        start_url = "/"
    
    site = get_current_site(request)
    manifest = {
        "name": site.name,
        "short_name": site.name,
        "icons": [],
        "start_url": "%s?from=manifest_json" % start_url,
        "display": "standalone",
    }
    if FCM_SENDER_ID:
        manifest['gcm_sender_id'] = FCM_SENDER_ID
    
    for icon in APP_ICON_URLS:
        # we cache this for 24 hours, so using Pillow is acceptable
        img_file = finders.find(icon)
        with Image.open(img_file) as img:
            manifest['icons'].append({
                "src": settings.STATIC_URL + icon,
                "sizes": "%dx%d" % (img.width, img.height),
                "type": "image/%s" % img.format.lower()
            })
    
    if APP_BACKGROUND_COLOR is not None:
        manifest['background_color'] = APP_BACKGROUND_COLOR
    if APP_THEME_COLOR is not None:
        manifest['theme_color'] = APP_THEME_COLOR
    
    return JsonResponse(manifest)


def _save(request):
    try:
        ua = request.META['HTTP_USER_AGENT'][:255]
    except (AttributeError, KeyError):
        ua = ''
    
    endpoint = request.POST.get('endpoint')
    logger.debug('Push save endpoint: %s' % endpoint)
    try:
        url_validate = URLValidator(schemes=['https',])
        url_validate(endpoint)
    except ValidationError:
        # chrome 44 and 45 sometimes give only unique part not full endpoint
        # url, workaround
        if endpoint and ua and 'Chrome' in ua:
            endpoint = "%s/%s" % (GCM_URL, endpoint)
            logger.debug('Fixed endpoint to: %s' % endpoint)
        else:
            # endpoint must be an url
            raise Http404('Wrong endpoint')
    
    key = request.POST.get('key', '')
    auth_secret = request.POST.get('auth_secret', '')
    
    timezone = request.POST.get('timezone')
    if timezone not in pytz.all_timezones:
        timezone = settings.TIME_ZONE
    
    try:
        subscr = DigestSubscription.objects.get(endpoint=endpoint)
    except DigestSubscription.DoesNotExist:
        subscr = DigestSubscription()
        subscr.endpoint = endpoint
    # actualize info anyway
    subscr.key = key
    subscr.auth_secret = auth_secret
    subscr.timezone = timezone
    subscr.ua = ua
    subscr.reactivate_if_needed()
    subscr.save()
    
    return JsonResponse({
        'response': {
            'status': 'ok',
            'id': subscr.pk,
        }
    })


@require_POST
@csrf_exempt
def save(request):
    # https://docs.djangoproject.com/en/1.8/ref/csrf/#view-needs-protection-for-one-path
    @csrf_protect
    def _protected_save(request):
        return _save(request)
    
    if USE_CSRF:
        return _protected_save(request)
    else:
        return _save(request)


def _deactivate(request):
    endpoint = request.POST.get('endpoint')
    
    try:
        subscr = DigestSubscription.objects.get(endpoint=endpoint)
    except DigestSubscription.DoesNotExist:
        raise Http404
    subscr.deactivate().save()
    
    return JsonResponse({
        'response': {
            'status': 'ok',
            'id': subscr.pk,
        }
    })


@require_POST
@csrf_exempt
def deactivate(request):
    # https://docs.djangoproject.com/en/1.8/ref/csrf/#view-needs-protection-for-one-path
    @csrf_protect
    def _protected_deactivate(request):
        return _deactivate(request)
    
    if USE_CSRF:
        return _protected_deactivate(request)
    else:
        return _deactivate(request)


def _notification_plus_one(what, id):
    """
    Statistics function (using raw SQL for speed).
    """
    cursor = connection.cursor()
    # what variable content is controlled in django routing
    # no security threats here
    cursor.execute("UPDATE %s SET %s=%s+1 WHERE id=%d" \
                    % (Task._meta.db_table, what, what, int(id)))


@never_cache
def notification_plus_one(request, what, id):
    """
    View to count views/closings statistics for push task.
    """
    _notification_plus_one(what, id)
    return HttpResponse(content='ok')


@never_cache
def last_notification(request):
    """
    Payload of the last actual and active push task for default timezone
    for old legacy push subscriptions what do not support payload encryption.
    """
    try:
        tz = TimezoneLayout.public_objects.filter(timezone=settings.TIME_ZONE)[0]
    except IndexError:
        raise Http404
    _notification_plus_one('views', tz.task.id)
    return JsonResponse({ 'notification': tz.task.get_payload(), })


@never_cache
def show_notification(request, id):
    try:
        task = Task.public_objects.get(pk=id)
    except Task.DoesNotExist:
        raise Http404
    _notification_plus_one('clicks', task.id)
    return redirect(task.url_relative(add_querystring={'from': 'push'}))
