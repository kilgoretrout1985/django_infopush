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


# must be top level function to be used in Pool
# receives only 1 param (tuple with all data)
def send_push_worker(data):
    (
        subscr_list,
        payload,
        ttl,
        gcm_key,
        vapid_key,
        vapid_email,
    ) = data
    
    responses = []
    exceptions = []  # can't use logger in a worker
    for subscr in subscr_list:
        try:
            if subscr.is_gcm(): 
                response = WebPusher( subscr.endpoint_and_keys() ).send(
                    data=payload if subscr.supports_payload() else None,
                    ttl=ttl,
                    timeout=3.0,
                    gcm_key=gcm_key,
                    # seems to be the only encoding legacy chrome understands
                    # for payload encryption
                    content_encoding="aesgcm"
                )
                responses.append( (subscr, response) )
            else:
                try:
                    response = webpush(
                        subscription_info=subscr.endpoint_and_keys(),
                        data=payload if subscr.supports_payload() else None,
                        ttl=ttl,
                        timeout=3.0,
                        vapid_private_key=vapid_key,
                        vapid_claims={"sub": "mailto:"+vapid_email,}
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
    """Command that sends push notifications"""
    
    help = 'Pushes notification to web-subscribers (cron use only)'
    
    DB_LIMIT = 7000  # get subscribers objs from DB by X at a time
    # Notification time to live (int seconds).
    # Google FCM has max ttl of 4 weeks.
    # For VAPID maximum is 86400 seconds (24 hours).
    TTL = 86400 - 1

    start_time = None
    pid_lock = None
    logger = None
    db_logger = None
    
    def __init__(self, *args, **kwargs):
        # protection against several copies of pushsend running at the same time
        self.pid_lock = PidLock(process=__file__)
        self.pid_lock.save_or_die()
        
        # everything (except destructor method) after save_or_die may not run
        # if another process is already running pushsend management command
        self.start_time = time.time()
        
        # setup custom logging if we have a folder for logs
        self.logger = logging.getLogger(__name__)
        log_dir = os.path.join(settings.BASE_DIR, 'log')
        if os.access(log_dir, os.F_OK) and os.access(log_dir, os.W_OK):
            self.logger.propagate = False
            self.logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
            self.logger.addHandler(logging.FileHandler(os.path.join(log_dir, 'pushsend.log')))
            if settings.DEBUG:
                self.db_logger = logging.getLogger('django.db.backends')  # log all SQL's
                self.db_logger.propagate = False
                self.db_logger.setLevel(logging.DEBUG)
                self.db_logger.addHandler(logging.FileHandler(
                    os.path.join(log_dir, 'pushsend_sql_debug.log')
                ))
        else:
            self.logger.addHandler(logging.NullHandler())
        
        self.logger.info("pushsend started at %s.", time.asctime(time.localtime(self.start_time)))
        super(Command, self).__init__(*args, **kwargs)
    
    def __del__(self):
        # May be None, if it is a duplicate process killed in save_or_die 
        # call in the constructor. If so, log nothing.
        if self.start_time is not None:
            end_time = time.time()
            self.logger.info("pushsend ended at %s.", time.asctime(time.localtime(end_time)))
            self.logger.info("pushsend worked for %f seconds.", (end_time - self.start_time))
        
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
            # can't filter by is_active=True, because after sending each pack
            # we disable erroneous subscriptions and this shifts the slice 
            # if only active objects selected.
            # TODO: This definitely needs optimisation some day.
            qs = DigestSubscription.objects \
                    .filter(timezone=tz_layout.timezone) \
                    .order_by('id')
            
            # send
            max_i = qs.count()
            # no more than DB_LIMIT objects at a time to save RAM
            for i in range(0, max_i, self.DB_LIMIT):
                subscriptions = qs[i:(i+self.DB_LIMIT)]
                active_subscriptions = [ s for s in subscriptions if s.is_active ]
                subscriptions = None
                if not active_subscriptions:
                    continue  # next pack if no active subscribers in this one
                
                max_workers = min(PUSHSEND_WORKERS, len(active_subscriptions))
                per_worker = [ active_subscriptions[i::max_workers] for i in range(max_workers) ]
                active_subscriptions = None
                
                pool_data = []
                for subscr_chunk in per_worker:
                    pool_data.append(
                        (
                            # different for each worker
                            subscr_chunk,
                            # common
                            json.dumps( task.get_payload() ),
                            self.TTL,
                            FCM_SERVER_KEY,
                            VAPID_PRIVATE_KEY,
                            VAPID_ADMIN_EMAIL,
                        )
                    )
                per_worker = None
                
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
                
                # can't use logger in workers, so log their exceptions here
                for subscr, e, timestamp in exceptions:
                    self.logger.error(
                        "%s, %s: %s, %s" % (
                            "Exception from push worker", 
                            time.asctime(time.localtime(timestamp)), 
                            type(e), e
                        )
                    )
                    # endpoint is not url
                    if isinstance(e, requests_ex.InvalidURL) \
                    or isinstance(e, requests_ex.URLRequired): 
                        subscr.deactivate().save()
                
                # changing DB from workers is also a problem
                for subscr, response in responses:
                    try:
                        self.logger.debug("Response for subscr %d" % subscr.pk)
                        self.logger.debug(response)
                        self.logger.debug(response.text)
                        
                        subscr.push_service_response_to_errors(
                            response.status_code,
                            response.text
                        )
                    except Exception as e:
                        self.logger.exception(
                            "%s, %s: %s" % (
                                "Exception while subscription error accounting", 
                                time.asctime(time.localtime(time.time())),
                                e
                            )
                        )
            
            tz_layout.done_at = timezone.now()
            tz_layout.save(update_fields=['done_at'])
            if task.all_timezones_done():
                task.done_at = timezone.now()
                task.save(update_fields=['done_at'])
    
    def clean_push_db(self):
        """
        Deletes old push task tzl and old in_active subscribers (db clean-up).
        """
        if randint(0, 299):
            return
        
        # Old tzls are almost useless. We only count task sending time on 
        # them, but this info is only needed for actual push tasks.
        tasks = Task.public_objects.filter(done_at__lt=( timezone.now() - timedelta(days=90) ))
        for task in tasks:
            task.timezonelayout_set.all().delete()
        
        # Delete only subscriptions that are inactive more than 1 year. 
        # Fresher subscriptions are left for statistics.
        DigestSubscription.objects.filter(
            is_active=False,
            deactivated_at__lt=( timezone.now() - timedelta(days=365) )
        ).delete()
