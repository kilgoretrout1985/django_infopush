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

from .settings import FCM_SENDER_ID, FCM_URL, APP_ICON_URLS, USE_CSRF, \
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
    # нам этот файл нужен, чтобы настроить gcm_sender_id
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
        "gcm_sender_id": FCM_SENDER_ID,
    }
    
    for icon in APP_ICON_URLS:
        # кеширование на сутки, так что тут все ок
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
        # chrome 44 и, кажется, 45 иногда передают только id без урла, костылим
        if endpoint and ua and 'Chrome' in ua:
            endpoint = "%s/%s" % (FCM_URL, endpoint)
            logger.debug('Fixed endpoint to: %s' % endpoint)
        else:
            # endpoint должен быть урлом или нах вообще всё это
            raise Http404('Wrong endpoint')
    
    # если юзер самостоятельно через браузер отпишется и подпишется потом,
    # у него изменится идентификатор подписки
    key = request.POST.get('key', '')
    auth_secret = request.POST.get('auth_secret', '')
    
    timezone = request.POST.get('timezone')
    if timezone not in pytz.all_timezones:
        timezone = settings.TIME_ZONE
    
    # поиск
    try:
        subscr = DigestSubscription.objects.get(endpoint=endpoint)
    except DigestSubscription.DoesNotExist:
        subscr = DigestSubscription()
        subscr.endpoint = endpoint
    # актуализация инфы
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
    Облегченная фактическая функция-учетчик статы (на живом SQL для скорости).
    Вынесена, чтобы можно было вызвать напрямую, не передавая request.
    """
    cursor = connection.cursor()
    cursor.execute("UPDATE %s SET %s=%s+1 WHERE id=%d" \
                    % (Task._meta.db_table, what, what, int(id)))


@never_cache
def notification_plus_one(request, what, id):
    """
    Вьюха учета просмотров|закрытий push-задания для статистики.
    """
    _notification_plus_one(what, id)
    return HttpResponse(content='ok')


@never_cache
def last_notification(request):
    """
    Возвращает данные о последнем актуальном задании
    (далее - актуальном для дефолтового часового пояса)
    для старых legacy-подписок, где нельзя шифровать данные.
    """
    try:
        # Выбираем последнее выполненное задание для дефолтового часового пояса.
        # Это старый обработчик для легаси подписок, которым мы не можем шифровать
        # данные, тк не знаем auth_secret, а раз не обновили auth_secret, то и
        # правильный часовой пояс у них не знаем (~97.3% случаев). Еще ~2.7%
        # случаев это новые подписки на некро-браузеры, которые имеют свой часовой
        # пояс, но не поддерживают шифрование - пох, такие будут отмирать и % падать.
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
