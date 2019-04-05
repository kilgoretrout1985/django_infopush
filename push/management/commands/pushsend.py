# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

from pywebpush import WebPusher, webpush, WebPushException
import urllib3
from requests import exceptions as requests_ex

import time
import logging
import os
from multiprocessing import Pool
import json
from random import randint
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from commonstuff.models import PidLock

from push.models import DigestSubscription, TimezoneLayout, Task
from push.settings import FCM_SERVER_KEY, PUSHSEND_WORKERS, VAPID_PRIVATE_KEY,\
                          VAPID_ADMIN_EMAIL


# setup custom logging if we have a folder for logs
logger = logging.getLogger(__name__)
log_dir = os.path.join(settings.BASE_DIR, 'log')
if os.access(log_dir, os.F_OK) and os.access(log_dir, os.W_OK):
    logger.propagate = False
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    logger.addHandler(logging.FileHandler(os.path.join(log_dir, 'pushsend.log')))
    if settings.DEBUG:
        db_logger = logging.getLogger('django.db.backends') # log all SQL's
        db_logger.propagate = False
        db_logger.setLevel(logging.DEBUG)
        db_logger.addHandler(logging.FileHandler(
            os.path.join(log_dir, 'pushsend_sql_debug.log')
        ))
else:
    logger.addHandler(logging.NullHandler())


# функция должна быть вынесена из класса, чтобы запускаться в Pool
# параметр она получает только один (в нашем случае tuple со всеми данными)
def send_push_worker(data):
    (
        subscr_list,
        payload,
        ttl,
    ) = data
    
    vapid_claims = { "sub": "mailto:"+VAPID_ADMIN_EMAIL, }
    responses = []
    exceptions = []  # can't use logger in a worker
    for subscr in subscr_list:
        try:
            if subscr.is_gcm(): 
                response = WebPusher( subscr.endpoint_and_keys() ).send(
                    data=payload if subscr.supports_payload() else None,
                    ttl=ttl,
                    timeout=2,
                    gcm_key=FCM_SERVER_KEY
                )
                responses.append( (subscr, response) )
            else:
                # minus 15 minutes for clock differences between our server and 
                # push service server. This is still better than default 
                # minus 12 hours in pywebpush lib
                vapid_claims["exp"] = int(time.time()) + ttl - 15*60,
                try:
                    response = webpush(
                        subscription_info=subscr.endpoint_and_keys(),
                        data=payload if subscr.supports_payload() else None,
                        ttl=ttl,
                        timeout=2,
                        vapid_private_key=VAPID_PRIVATE_KEY,
                        vapid_claims=vapid_claims
                    )
                    responses.append( (subscr, response) )
                except WebPushException as e:
                    # WebPushException got response object but we need to count
                    # error points on subscriptions
                    responses.append( (subscr, e.response) )
        except Exception as e:
            exceptions.append( (subscr, e, time.time(),) )
    
    return (responses, exceptions)


class Command(BaseCommand):
    """Рассылает push-уведомления по крону"""
    
    help = 'Pushes notification to web-subscribers (cron use only)'
    
    DB_LIMIT = 7000  # чтобы не сожрало память, подписчики из базы выбираются по X штук
    # Время жизни сообщения (int секунд).
    # None - поле вообще не будет задаваться нами для сообщения.
    # 0 - для Mozilla это, кажется, сразу убирать уведомление после получения.
    # FCM утверждает, что максимальное время у них 4 недели.
    # для VAPID 86400 секунд - это макс по стандарту
    TTL = 86400 - 1  # Пока так (больше и не нужно по факту)

    start_time = None
    pid_lock = None
    
    def __init__(self, *args, **kwargs):
        # protection against several copies of pushsend running at the same time
        self.pid_lock = PidLock(process=__file__)
        self.pid_lock.save_or_die()
        
        # все что после save_or_die может не выполниться,
        # если другой процесс уже выполняет команду
        
        self.start_time = time.time()
        logger.info("pushsend started at %s.", time.asctime(time.localtime(self.start_time)))
        super(Command, self).__init__(*args, **kwargs)
    
    def __del__(self):
        # может быть None, если это дублирующий процесс, который будет
        # убит в вызове save_or_die из конструктора
        if self.start_time is not None:
            end_time = time.time()
            logger.info("pushsend ended at %s.", time.asctime(time.localtime(end_time)))
            logger.info("pushsend worked for %f seconds.", (end_time - self.start_time))
        
        if self.pid_lock and self.pid_lock.pk:
            self.pid_lock.delete()

    def handle(self, *args, **options):
        urllib3.disable_warnings()
        self.clean_push_db()
        
        tz_layouts = list(TimezoneLayout.undone_objects.all())
        for tz_layout in tz_layouts:
            task = tz_layout.task
            
            tz_layout.started_at = timezone.now()
            tz_layout.save(update_fields=['started_at'])
            if not task.started_at:
                task.started_at = timezone.now()
                task.save(update_fields=['started_at'])
            
            # subscribers
            # Не можем отфильтровать здесь по is_active=True, т.к. сразу после
            # отправки в случае определенных ошибок выключаем часть подписок.
            # Это сдвигает срез выборки по active и тогда у пограничных между
            # пачками будет двойная рассылка. Поэтому отфильтруем активные перед
            # отправкой средствами питона, а не БД (вообще надо будет переделать).
            qs = DigestSubscription.objects \
                    .filter(timezone=tz_layout.timezone) \
                    .order_by('id')
            
            # send
            max_i = qs.count()
            # выбираем пачками из БД, чтобы объекты не пожрали память
            for i in range(0, max_i, self.DB_LIMIT):
                subscriptions = qs[i:(i+self.DB_LIMIT)]
                active_subscriptions = [ s for s in subscriptions if s.is_active ]
                subscriptions = None  # освободить память
                if not active_subscriptions:
                    continue  # next pack if no active subscribers in this one
                
                # разбиваем на кол-во частей или по кол-ву подписок, если их меньше чем ядер
                max_workers = min(PUSHSEND_WORKERS, len(active_subscriptions))
                per_worker = [ active_subscriptions[i::max_workers] for i in range(max_workers) ]
                active_subscriptions = None  # освобождаем память
                
                pool_data = []
                for subscr_chunk in per_worker:
                    pool_data.append(
                        (
                            # различаются
                            subscr_chunk,
                            # общие для всех вызовов
                            json.dumps( task.get_payload() ),
                            self.TTL,
                        )
                    )
                per_worker = None  # освобождаем память
                
                if max_workers == 1:
                    responses, exceptions = send_push_worker(pool_data[0])
                else:
                    pool = Pool(processes=max_workers)
                    multi_result = pool.map(send_push_worker, pool_data)
                    # https://stackoverflow.com/questions/20914828/python-multiprocessing-pool-join-not-waiting-to-go-on
                    # https://stackoverflow.com/questions/25391025/what-exactly-is-python-multiprocessing-modules-join-method-doing
                    pool.close()
                    pool.join()
                    responses = []
                    exceptions = []
                    # flattern result list
                    for result in multi_result:
                        responses += result[0]
                        exceptions += result[1]
                    multi_result = None
                pool_data = None
                
                # logger нельзя передавать в воркеры, поэтому залогим
                # полученные exceptions сейчас
                for subscr, e, timestamp in exceptions:
                    localtime = time.asctime(time.localtime(timestamp))
                    logger.error("%s, %s: %s, %s" % (__name__, localtime, type(e), e))
                    # endpoint is not url
                    if isinstance(e, requests_ex.InvalidURL) \
                    or isinstance(e, requests_ex.URLRequired): 
                        subscr.deactivate().save()
                
                # с изменениями БД в воркерах тоже непонятно как все работает
                for subscr, response in responses:
                    try:
                        logger.debug("Response for subscr %d" % subscr.pk)
                        logger.debug(response)
                        logger.debug(response.text)
                        subscr.push_service_response_to_errors(response.text)
                    except Exception as e:
                        localtime = time.asctime( time.localtime(time.time()) )
                        logger.exception("%s, %s: %s, %s" % (__name__, localtime, type(e), e))
            
            # запишем результаты наших стараний в БД
            tz_layout.done_at = timezone.now()
            tz_layout.save(update_fields=['done_at'])
            if task.all_timezones_done():
                task.done_at = timezone.now()
                task.save(update_fields=['done_at'])
    
    def clean_push_db(self):
        """
        Чистка старых tzl и неактивных подписок, чтобы таблица не разросталась.
        """
        if randint(0, 299):
            return
        
        # Старые tzl занимают место и раздувают таблицу (по которой активно
        # идет поиск во вьюхе last_notification). Единственная инфа, которую мы
        # берем оттуда это время, потраченное на рассылку, но она нужна только
        # для актуальных заданий и не имеет ценности для старья.
        tasks = Task.public_objects.filter(done_at__lt=( timezone.now() - timedelta(days=90) ))
        for task in tasks:
            task.timezonelayout_set.all().delete()
        
        # т.к. мы перебираем все подписки, а не только активные, то старые записи
        # скорее всего серьезно замедляют рассылку (но все не удаляем, чтобы можно
        # было собрать статистику при необходимости)
        DigestSubscription.objects.filter(
            is_active=False,
            deactivated_at__lt=( timezone.now() - timedelta(days=365) )
        ).delete()
