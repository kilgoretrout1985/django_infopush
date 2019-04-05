# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

from django.conf import settings

VAPID_PUBLIC_KEY = getattr(settings, 'DJANGO_INFOPUSH_VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = getattr(settings, 'DJANGO_INFOPUSH_VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = getattr(settings, 'DJANGO_INFOPUSH_VAPID_ADMIN_EMAIL', '')

FCM_SERVER_KEY = getattr(settings, 'DJANGO_INFOPUSH_FCM_SERVER_KEY', '')
FCM_SENDER_ID = getattr(settings, 'DJANGO_INFOPUSH_FCM_SENDER_ID', '')

# how many processes to use in a pushsend management command for parallel push
# 1 disables multiprocessing
PUSHSEND_WORKERS = int(getattr(settings, 'DJANGO_INFOPUSH_PUSHSEND_WORKERS', 3))

# default push icon
DEFAULT_ICON_URL = getattr(settings, 'DJANGO_INFOPUSH_DEFAULT_ICON_URL', "/static/push/img/icon.png")
MIN_ICON_W = int(getattr(settings, 'DJANGO_INFOPUSH_MIN_ICON_W', 192))
MIN_ICON_H = int(getattr(settings, 'DJANGO_INFOPUSH_MIN_ICON_H', 192))
# kb, max filesize of push icon
ICON_CUSTOM_MAX_FILESIZE = int(getattr(settings, 'DJANGO_INFOPUSH_ICON_CUSTOM_MAX_FILESIZE', 25))

# big push image for push in Chrome
# best aspect ration is 3:2 for desktop Chrome
# mobile Chrome will crop it vertically a little
# https://web-push-book.gauntface.com/chapter-05/02-display-a-notification/#image
MIN_BIG_IMAGE_W = int(getattr(settings, 'DJANGO_INFOPUSH_MIN_BIG_IMAGE_W', 1023))
MIN_BIG_IMAGE_H = int(getattr(settings, 'DJANGO_INFOPUSH_MIN_BIG_IMAGE_H', 682))
# kb, max filesize for big image
BIG_IMAGE_MAX_FILESIZE = int(getattr(settings, 'DJANGO_INFOPUSH_BIG_IMAGE_MAX_FILESIZE', 100))

# web-site as an "app" in manifest.json
# https://developers.google.com/web/updates/2014/11/Support-for-installable-web-apps-with-webapp-manifest-in-chrome-38-for-Android
APP_ICON_URLS = getattr(settings, 'DJANGO_INFOPUSH_APP_ICON_URLS', ["push/img/app_icon.png",])
# optional, https://developers.google.com/web/updates/2015/08/using-manifest-to-set-sitewide-theme-color
APP_THEME_COLOR = getattr(settings, 'DJANGO_INFOPUSH_APP_THEME_COLOR', None)
# optional, https://developers.google.com/web/tools/lighthouse/audits/custom-splash-screen
APP_BACKGROUND_COLOR = getattr(settings, 'DJANGO_INFOPUSH_APP_BACKGROUND_COLOR', None)

# error threshold after which we disable push subscription
ERROR_THRESHOLD = int(getattr(settings, 'DJANGO_INFOPUSH_ERROR_THRESHOLD', 30))

# do not change, it is here for easy import of this constant
GCM_URL = 'https://android.googleapis.com/gcm/send'
FCM_URL = 'https://fcm.googleapis.com/fcm/send'

# this setting allows to disable CSRF for django_infopush views only, if needed
USE_CSRF = bool(getattr(settings, 'DJANGO_INFOPUSH_USE_CSRF', True))