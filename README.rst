===============
django_infopush
===============

django_infopush is a Django reusable app, that allows to gather push
subscriptions and send web push notifications to browsers.

**It is a full featured reusable app which includes::**

* frontend & backend code which gathers push subscriptions and saves them to DB,
* service worker to show notifications, manage clicks and basic notification
statistics,
* django admin interface where you create new push tasks (title, text, icon,
url, image, time to send),
* django management command to perform your tasks (send notifications to
subscribers).

This app covers 99% webpush needs for content web-sites than you just want
to send an announcement of a new blog post for example. Just make a new push
task in the admin and job is done. For the same reason this app will not suite
those who need the ability to send individual pushes to each subscriber.

**Known limitations are::**

* django_infopush works on Python 3 only (2.7 support will be added).
* Tested only on Django 1.11 LTS.
* Like any webpush app it requires you website to work on SSL (httpS://).
* You better have access to CRON on your server, because push tasks are send
using `python manage.py pushsend` management command. And running it manually
every time sounds like a bad idea. Although for testing purposes manual calls
will do well.
* django_infopush currently uses Google FCM, not VAPID. If you do not know what
it means, let's say VAPID is the future ot webpush, and FCM is the past, which
nevertheless works fine. VAPID support will be added someday.

Quick start
-----------

1. `pip install django_infopush`

2. Add "push" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'push',
    ]

3. Enable sites framework in Django, see `official docs
   <https://docs.djangoproject.com/en/1.11/ref/contrib/sites/#enabling-the-sites-framework>`_.

4. Configure django_infopush in your project settings.py file. At least your
   FCM id and key *(see docs/SETTINGS.rst)*.

5. Run `python manage.py migrate` to create push models.

6. Include URLconf in your project urls.py like this::

    from django.conf import settings
    from django.views.generic import TemplateView
    from django.views.decorators.cache import cache_page

    url(r'^push/', include('push.urls')),
    url(r'^service-worker.js$', cache_page(1 if settings.DEBUG else 86400)(TemplateView.as_view(
        template_name="push/service-worker.js",
        content_type='application/javascript; charset='+settings.DEFAULT_CHARSET,
    )), name='service-worker.js'),

7. Add `{% include 'push/_head_include.html' %}` into head-section of your
   django-project's html template(s). Do not include it on the pages where you
   don't want to see push-subscribe browser window. Visit your website to become
   first subscriber (currently Chrome and FF support webpush, not Safari).

8. Visit http://127.0.0.1:8000/admin/push/ to create first push task.

9. CRON setup for `python manage.py pushsend` management command
   (every 5-10 minutes). You can also run this command manually for testing
   purposes.

10. (OPTIONAL) Run `python manage.py test push` for basic check of the app.
