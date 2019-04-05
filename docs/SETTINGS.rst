You have to define these variables in settings.py file of your Django project.

==================
Mandatory Settings
==================

**DJANGO_INFOPUSH_VAPID_PUBLIC_KEY**

**DJANGO_INFOPUSH_VAPID_PRIVATE_KEY**

Your public and private keys for VAPID authorization. You can simply generate
them `here <https://web-push-codelab.glitch.me/>`_ in a second.

Without these keys you can only push-subscribe Firefox, not Chrome. Chrome
requires keys for VAPID subscriptions, so you better set them up in your
project.

(both are `str`, defaults to empty string).

**DJANGO_INFOPUSH_VAPID_ADMIN_EMAIL**

VAPID spec advises to set your site/server admin or support address,
so that push-server administration can reach you if something goes wrong.

(`str`, defaults to empty string).

=================
Optional settings
=================

**DJANGO_INFOPUSH_PUSHSEND_WORKERS**

How many processes to use in pushsend management command for parallel
push (int, default `3`).

Set it to `1` to disable multiprocessing in pushsend command.

**DJANGO_INFOPUSH_DEFAULT_ICON_URL**

Relative path (no domain) to notification icon, which is used by default
if you haven't uploaded custom icon for a push task (str).

JPG, PNG, GIF (first frame used from gifs), square shape.

Default value is "/static/push/img/icon.png"

**DJANGO_INFOPUSH_MIN_ICON_W**

The minimum width in px of the push icon (int, default 192).

**DJANGO_INFOPUSH_MIN_ICON_H**

The minimum height in px of the push icon (int, default 192).

**DJANGO_INFOPUSH_ICON_CUSTOM_MAX_FILESIZE**

The maximum filesize of a custom notification icon (you can attach your own
to each notification).

In kb (int, default 25).

**DJANGO_INFOPUSH_MIN_BIG_IMAGE_W**

The minimum width in px of the big picture for push in Chrome.
(int, default is 1023).

Read more `here
<https://web-push-book.gauntface.com/chapter-05/02-display-a-notification/#image>`_.

**DJANGO_INFOPUSH_MIN_BIG_IMAGE_H**

The minimum height in px of the big picture for push in Chrome.

(int, default is 682).

**DJANGO_INFOPUSH_BIG_IMAGE_MAX_FILESIZE**

Maximum filesize of a large notification picture (you can attach your own to
each notification).

In kilobytes (int, default 100).

**DJANGO_INFOPUSH_APP_ICON_URLS**

Web push requires manifest.json, in which we also configure the web application,
so that in Chrome on Android you can save the "shortcut" to the website on
your desktop. This array of paths relative(!) to django static-dir will be the
icons for the "shortcut" (list of strings).

Only PNG, square. Several identical icons in different sizes.
192*192, 512*512, Read more `here
<https://developers.google.com/web/updates/2014/11/Support-for-installable-web-apps-with-webapp-manifest-in-chrome-38-for-Android>`_.

Default is `["push/img/app_icon.png"]`. It is better to change on your own,
this is very common.

**DJANGO_INFOPUSH_APP_BACKGROUND_COLOR**

When launching an "application" site from the desktop, splash screen can be
used. Set the background of this screen, for example #CCCCCC
(str, default is None, not used).

Read more `here
<https://developers.google.com/web/updates/2015/10/splashscreen>`_.

**DJANGO_INFOPUSH_APP_THEME_COLOR**

Color code to "brand" the browser (mobile Chrome) under the site.
For example #CCCCCC (str, default is None, not used).

Read more `here
<https://developers.google.com/web/updates/2015/08/using-manifest-to-set-sitewide-theme-color>`_.

**DJANGO_INFOPUSH_ERROR_THRESHOLD**

The number of error points, after which we disable push-subscription (int, by default 30).

**DJANGO_INFOPUSH_USE_CSRF**

Allows you to turn off CSRF checking on push views. Sometimes it can be helpful
(bool, default is True - CSRF works).

**DJANGO_INFOPUSH_FCM_SERVER_KEY**

Key of your Google FCM project (str).
Left for backward compatibily - sending pushes to old FCM/GCM subscriptions
that already exist.

Get it by using `this docs
<https://developers.google.com/web/updates/2015/03/push-notifications-on-the-open-web#make_a_project_on_the_firebase_developer_console>`_.

**DJANGO_INFOPUSH_FCM_SENDER_ID**

ID of your Google FCM project (str).
Left for backward compatibily - sending pushes to old FCM/GCM subscriptions
that already exist.

Get it by using `this docs
<https://developers.google.com/web/updates/2015/03/push-notifications-on-the-open-web#make_a_project_on_the_firebase_developer_console>`_.
