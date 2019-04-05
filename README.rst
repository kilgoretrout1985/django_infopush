===============
django_infopush
===============

django_infopush is a Django reusable app, that allows to gather push
subscriptions and send web push notifications to browsers.

**It is a full featured reusable app which includes:**

* frontend & backend code which gathers push subscriptions and saves them to DB,
* service worker to show notifications, manage clicks and basic notification statistics,
* django admin interface where you create new push tasks (title, text, icon, url, image, time to send) and view stats for the old ones,
* django management command to perform your tasks (send notifications to subscribers).

.. image:: https://raw.githubusercontent.com/kilgoretrout1985/django_infopush/master/docs/img/push_admin_list_thumb.png
   :target: https://raw.githubusercontent.com/kilgoretrout1985/django_infopush/master/docs/img/push_admin_list.png

This app covers 99% webpush needs for content web-sites than you just want
to send an announcement of a new blog post for example. Just make a new push
task in the admin and job is done.

.. image:: https://raw.githubusercontent.com/kilgoretrout1985/django_infopush/master/docs/img/push_admin_add_thumb.png
   :target: https://raw.githubusercontent.com/kilgoretrout1985/django_infopush/master/docs/img/push_admin_add.png

**Known limitations are:**

* Tested only on Django 1.11 LTS.
* You better have access to CRON on your server, because push tasks are send using `python manage.py pushsend` management command. And running it manually every time sounds like a bad idea. Although for testing purposes manual calls will do well.

Quick start
-----------

1. `pip install django_infopush`

2. Add "commonstuff" and "push" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        # ...
        'commonstuff',
        'push',
    ]

3. Enable sites framework in Django, see `official docs
   <https://docs.djangoproject.com/en/1.11/ref/contrib/sites/#enabling-the-sites-framework>`_.

4. Configure django_infopush in your project settings.py file. At least your
   DJANGO_INFOPUSH_VAPID_PUBLIC_KEY and DJANGO_INFOPUSH_VAPID_PRIVATE_KEY
   (you can simply generate them `here <https://web-push-codelab.glitch.me/>`_).

   You also have to set DJANGO_INFOPUSH_VAPID_ADMIN_EMAIL with your
   site admin or support address, so that push-server administration can
   reach you if something goes wrong.

   E.g.::

    DJANGO_INFOPUSH_VAPID_PUBLIC_KEY = 'AHf42JhrMtFOXAG2OYTmEoBvKNcEsxmYF5pqvYd4InFEEU0x41HzymPQRtcvJZp9iNpDQK4GuTGMWAgn0E8G8IZ'
    DJANGO_INFOPUSH_VAPID_PRIVATE_KEY = 'CcmbGJ9wce7596DoObRzyPHNktPRo5CSCdericz7Pf7'
    DJANGO_INFOPUSH_VAPID_ADMIN_EMAIL = 'admin@mysite.com'

   See `docs/SETTINGS.rst
   <https://github.com/kilgoretrout1985/django_infopush/blob/master/docs/SETTINGS.rst>`_
   for more.

5. Run `python manage.py migrate` to create push models.

6. Include URLconf in your project urls.py like this::

    from django.conf.urls import url, include
    from django.conf import settings
    from django.views.generic import TemplateView
    from django.views.decorators.cache import cache_page

    urlpatterns = [
        # ...
        url(r'^push/', include('push.urls')),
        url(r'^service-worker.js$', cache_page(1 if settings.DEBUG else 86400)(TemplateView.as_view(
            template_name="push/service-worker.js",
            content_type='application/javascript; charset='+settings.DEFAULT_CHARSET,
        )), name='service-worker.js'),
    ]

7. Add `{% include 'push/_head_include.html' %}` into head-section of your
   django-project's html template(s). Do not include it on the pages where you
   don't want to see push-subscribe browser window. Visit your website to become
   first subscriber (currently Chrome and FF support webpush, not Safari).

8. Visit http://127.0.0.1:8000/admin/push/ to create first push task.

9. CRON setup for `python manage.py pushsend` management command
   (every 5-10 minutes). You can also run this command manually for testing
   purposes.

10. (OPTIONAL) Run `python manage.py test push` for basic check of the app.
