# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

import pytz

from django.utils.six.moves.urllib.parse import urlparse, urlunparse, parse_qs,\
                                                urlencode
import json
from datetime import timedelta

from django.db import models, transaction, IntegrityError
from django.utils import timezone
from django.utils.html import mark_safe
from django.urls import reverse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible

from commonstuff.models_base import ModelWith2Images

from .settings import DEFAULT_ICON_URL, ERROR_THRESHOLD, GCM_URL


# http://stackoverflow.com/questions/27072222/django-1-7-1-makemigrations-fails-when-using-lambda-as-default-for-attribute
def _timezone_now():
    return timezone.now()


class BaseSubscription(models.Model):
    """Base class for push subscriptions"""
    
    endpoint = models.CharField(_('endpoint'), max_length=255, unique=True, editable=False)
    key = models.CharField(_('key'), max_length=255, blank=True, default='', editable=False)
    auth_secret = models.CharField(_('auth secret'), max_length=255, blank=True, default='', editable=False)
    is_active = models.BooleanField(_('is active'), default=True, db_index=True)
    errors = models.PositiveIntegerField(_('send errors'), default=0, editable=False)
    ua = models.CharField(_('useragent'), max_length=255, editable=False)
    timezone = models.CharField(
        _('timezone'), max_length=48,
        choices=((x,x) for x in sorted(pytz.all_timezones_set)),
        db_index=True
    )
    created_at = models.DateTimeField(_('created'), default=_timezone_now, editable=False)
    activated_at = models.DateTimeField(_('activated'), blank=True, null=True, editable=False)
    deactivated_at = models.DateTimeField(_('deactivated'), blank=True, null=True, editable=False)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        if self.is_active and self.activated_at is None:
            self.activated_at = timezone.now()
        return super(BaseSubscription, self).save(*args, **kwargs)
    
    @classmethod
    def count_active(cls):
        return cls.objects.filter(is_active=True).count()
    
    def endpoint_truncated(self):
        return "%s..." % self.endpoint[0:64]
    endpoint_truncated.admin_order_field = 'endpoint'
    endpoint_truncated.short_description = _('endpoint')

    def is_gcm(self):
        """Is it an old Google subscription (they have own sending algo)"""
        return self.endpoint.startswith(GCM_URL)
    
    def supports_payload(self):
        return bool(self.key and self.auth_secret)
    
    def endpoint_and_keys(self):
        """
        Subscription info for payload encryption in a format of
        https://developer.mozilla.org/ru/docs/Web/API/PushSubscription/toJSON
        """
        d = { "endpoint": self.endpoint, }
        if self.supports_payload():
            d['keys'] = {
                "auth": self.auth_secret,
                "p256dh": self.key,
            }
        return d
    
    def deactivate(self):
        if self.is_active:
            self.is_active = False
            self.deactivated_at = timezone.now()
        return self
    
    def reactivate_if_needed(self):
        if self.id:
            self.errors = 0
            if not self.is_active:
                self.is_active = True
                self.activated_at = timezone.now()
        return self
    
    def errors_accounting(self, quantity=1):
        if quantity > 0:
            self.errors += quantity
            if self.errors >= ERROR_THRESHOLD:
                self.deactivate()
        elif quantity < 0:
            # subscription had errors, but it's ok now, so decrease error counter
            if self.errors > 0:
                self.errors += quantity  # negative number here
                if self.errors < 0:
                    self.errors = 0
        return self
    
    def push_service_response_to_errors(self, response):
        """
        Parse response from remote push-server.
        
        Penalize erroneous subscriptions, removes points from successful delivery.
        Receives the response body of the push server (json str or dict).
        """
        if response and not isinstance(response, dict):
            response = json.loads(response)
        
        if self.is_gcm():
            return self.__fcm_push_service_response_to_errors(response)
        else:
            return self.__normal_push_service_response_to_errors(response)
    
    def __normal_push_service_response_to_errors(self, response):
        # For non(!)-success responses, an extended error code object will be returned
        if response:  # we have an error
            if response['code'] < 300:
                return self
            # http://autopush.readthedocs.io/en/latest/http.html#response
            # https://developers.google.com/web/fundamentals/push-notifications/web-push-protocol#response_from_push_service
            error_points = 0 # default for 401, 413, 429, 500, 503...
            if response['code'] == 301:
                error_points = 3
            elif response['code'] in (404, 410):
                error_points = 15
            if error_points:
                self.errors_accounting(error_points).save()
        else:  # ok
            # check so we don't query database for no reason
            if self.errors > 0:
                self.errors_accounting(-1).save()
        return self
    
    def __fcm_push_service_response_to_errors(self, response):
        response_result = response['results'][0]  # part we need
        # ok, decrease error counter
        if 'message_id' in response_result:
            if self.errors > 0:
                self.errors_accounting(-1).save()
            # If registration_id is set, replace the original ID with the new value
            # (canonical ID) in your server database.
            if 'registration_id' in response_result:
                new_endpoint = response_result['registration_id']
                try:
                    # it's not clear from the FCM docs if they respond
                    # with the full URL or only a endpoint part
                    url_validate = URLValidator(schemes=['https',])
                    url_validate(new_endpoint)
                except ValidationError:
                    new_endpoint = "%s/%s" % (GCM_URL, new_endpoint)
                self.endpoint = new_endpoint
                try:
                    self.save()
                except IntegrityError as e:
                    # Duplicate entry for endpoint - new canonical endpoint
                    # is already stored in the DB 
                    pass
        elif 'error' in response_result:
            error_code = response_result['error']
            # https://firebase.google.com/docs/cloud-messaging/http-server-ref#error-codes
            if error_code in ('NotRegistered', 'InvalidRegistration',):
                # google docs say we should turn off these subscriptions immediately
                # but lets give them one more chance (based on testing responses manually)
                self.errors_accounting(+15).save()
            # The server couldn't process the request in time. Retry the same request
            elif error_code in ('Unavailable', 'InternalServerError',):
                pass
            # misc errors
            else:
                self.errors_accounting(+1).save()
        return self


@python_2_unicode_compatible
class DigestSubscription(BaseSubscription):
    """Digest push subscription (the only actual subscription type for now)"""
    
    class Meta:
        verbose_name = _('push subscription')
        verbose_name_plural = _('push subscriptions')
    
    def __str__(self):
        return _('subscription ID %(pk)d') % { 'pk': self.id }


class PublicTaskManager(models.Manager):
    """Push tasks, that are available for subscribers"""
    def get_queryset(self):
        return super(PublicTaskManager, self).get_queryset() \
                    .filter(is_active=True) \
                    .exclude(started_at__isnull=True)


@python_2_unicode_compatible
class Task(ModelWith2Images):
    """Push tasks (the task here is to send something to push subscribers)"""
    
    title = models.CharField(_('title'), max_length=61)
    message = models.TextField(_('message'), max_length=122)
    url = models.URLField(
        _('url'), max_length=512,
        help_text=_('If there is no from param in url, ?from=push will be added automatically.')
    )
    is_active = models.BooleanField(
        _('active'), default=False, db_index=True,
        help_text=_('Is it an active task that should be done, or a draft.')
    )
    views = models.PositiveIntegerField(_('views'), default=0, editable=False)
    clicks = models.PositiveIntegerField(_('clicks'), default=0, editable=False)
    closings = models.PositiveIntegerField(
        _('closings'), default=0, editable=False,
        help_text=_('When user closes the notification.')
    )
    created_at = models.DateTimeField(_('created'), default=_timezone_now, editable=False)
    run_at = models.DateTimeField(
        _('run at'), default=_timezone_now, db_index=True,
        help_text=_('Send time here is set according to subscriber\'s timezone! Also you can postpone sending.')
    )
    started_at = models.DateTimeField(
        _('started at'), blank=True, null=True, db_index=True, editable=False,
        help_text=_('When we started to send this task.')
    )
    done_at = models.DateTimeField(
        _('done at'), blank=True, null=True, db_index=True, editable=False,
        help_text=_('When work on this task has been done.')
    )
    
    objects = models.Manager()  # default: all rows
    public_objects = PublicTaskManager()
    
    class Meta:
        verbose_name = _('push task')
        verbose_name_plural = _('push tasks')
    
    def __str__(self):
        return '%(verbose_name)s "%(current_title)s"' % {
            'verbose_name': self._meta.verbose_name,
            'current_title': self.title,
        }
    
    def get_absolute_url(self):
        return reverse('push_show_notification', args=[self.id,])
    
    def is_done(self):
        return self.done_at is not None
    is_done.admin_order_field = 'done_at'
    is_done.boolean = True
    is_done.short_description = _('done')
    
    def ctr(self, raw=False):
        """For admin interface"""
        try:
            ctr = self.clicks * 100.0 / self.views
            return ctr if raw else "%0.2f%%" % ctr
        except ZeroDivisionError:
            return None if raw else 'n/a'
    ctr.short_description = _('CTR')
    
    def closings_percent(self, raw=False):
        """For admin: rejections to views task ratio"""
        try:
            dtr = self.closings * 100.0 / self.views
            if raw:
                return dtr
            else:
                txt = _('%(num_closings)d times users rejected this notification') \
                    % { 'num_closings': self.closings }
                return mark_safe('<span title="%s">%0.2f%%</span>' % (txt, dtr))
        except ZeroDivisionError:
            return None if raw else 'n/a'
    closings_percent.short_description = _('rejections')
    
    def run_for(self, with_microseconds=False):
        """How much time we spend sending this task (textual representation for admin)"""
        if self.started_at is None:
            return None
        td = timedelta()
        for tzl in self.timezonelayout_set.all():
            td = td + tzl.run_for()
        if not with_microseconds:
            td = td - timedelta(microseconds=td.microseconds)
        return td if td != timedelta() else None
    run_for.short_description = _('run for')

    def url_relative(self, add_querystring={}):
        """Relative push-task url without domain for service worker"""
        # break url to components
        parts = urlparse(self.url)
        # add querystring if needed
        if add_querystring:
            qs = parse_qs(parts[4])
            for k in qs:
                # The dictionary keys are the unique query variable names
                # and the values are lists of values for each name
                qs[k] = qs[k][0]
            add_querystring.update(qs)
            parts = parts[0:4] + (urlencode(add_querystring),) + parts[5:]
        # join url from parts ignoring host and port
        return urlunparse(('', '') + parts[2:])
    
    def get_payload(self):
        """Task info we send to push-subscribers"""
        payload = {
            'title': self.title,
            'message': self.message,
            'icon': self.image.url if self.has_image() else DEFAULT_ICON_URL,
            'tag': 'notification-digest',
            'url': self.get_absolute_url(),
            'views_stat_url': reverse('push_notification_plus_one', args=['views', self.id,]),
            'closings_stat_url': reverse('push_notification_plus_one', args=['closings', self.id,]),
        }
        if self.has_image2():
            payload['image'] = self.image2.url
        return payload
    
    def all_timezones_done(self):
        return not self.timezonelayout_set.filter(done_at__isnull=True).exists()
    
    def save(self, *args, **kwargs):
        ret = super(Task, self).save(*args, **kwargs)
        
        # sending time can be edited only for tasks that are not started yet
        if self.started_at is None:
            # we check that task start time has changed by checking only
            # one timezone (otherwise admin push interface will be very slow)
            if len(pytz.all_timezones_set) == self.timezonelayout_set.count():
                test_layout_tz = self.timezonelayout_set.get(timezone=settings.TIME_ZONE)
                # empty timedelta means these datetimes are equal
                if self.run_at - test_layout_tz.run_at == timedelta():
                    return ret
            
            # detect hour only(!) for project's default timezone
            default_tz = pytz.timezone(settings.TIME_ZONE)  # project's timezone
            run_at_in_default_tz = default_tz.normalize( self.run_at.astimezone(default_tz) )
            # hour int for project's timezone (not UTC)
            # like the time editor sees in push admin interface
            # e.g. 10 for 07:30:00 UTC == 10:30:00 Europe/Moscow
            run_at_hour = int(run_at_in_default_tz.hour)
            
            # update layout db here
            with transaction.atomic():
                self.timezonelayout_set.all().delete()
                for tz_str in pytz.all_timezones_set:
                    tz = pytz.timezone(tz_str)
                    tzed_run_at = tz.normalize( self.run_at.astimezone(tz) )
                    # e.g. for Asia/Ekaterinburg it will be 10:30:00 Asia/Ekaterinburg
                    tzed_run_at = tzed_run_at.replace(hour=run_at_hour)
                    self.timezonelayout_set.create(
                        timezone=tz_str,
                        # Django ORM will change it to 05:30:00 UTC then saving
                        # to db that does not support timezones (mysql)
                        # TODO: wtf will happen for DB's that support timezones ???
                        run_at=tzed_run_at
                    )
        return ret


class UndoneTZLManager(models.Manager):
    """Timezone sub-tasks that have to be done"""
    def get_queryset(self):
        return super(UndoneTZLManager, self).get_queryset().filter(
            task__is_active=True,
            run_at__lte=timezone.now(),
            done_at__isnull=True,
            started_at__isnull=True
        ).order_by('run_at')


class PublicTZLManager(models.Manager):
    """Push sub-tasks, that are already available for subscribers"""
    def get_queryset(self):
        return super(PublicTZLManager, self).get_queryset() \
                    .filter(task__is_active=True) \
                    .exclude(started_at__isnull=True) \
                    .order_by('-run_at')


@python_2_unicode_compatible
class TimezoneLayout(models.Model):
    """
    Push task sub-tasks by timezone
    (so that users get "pushed" for the time in their local timezone).
    """
    task = models.ForeignKey(Task, editable=False, on_delete=models.CASCADE)
    timezone = models.CharField(
        _('timezone'), max_length=48,
        choices=((x,x) for x in sorted(pytz.all_timezones_set)),
        db_index=True, editable=False
    )
    run_at = models.DateTimeField(_('run at'), default=_timezone_now, db_index=True, editable=False)
    started_at = models.DateTimeField(_('started at'), blank=True, null=True, db_index=True, editable=False)
    done_at = models.DateTimeField(_('done at'), blank=True, null=True, db_index=True, editable=False)
    
    objects = models.Manager()
    undone_objects = UndoneTZLManager()
    public_objects = PublicTZLManager()
    
    class Meta:
        unique_together = ('task', 'timezone',)
    
    def __str__(self):
        return _('%(timezone)s tz sub-task for %(task)s') % {
            'timezone': self.timezone,
            'task': self.task
        }
    
    def run_for(self):
        if self.done_at is None or self.started_at is None:
            return timedelta()  # zero timedelta
        return self.done_at - self.started_at
