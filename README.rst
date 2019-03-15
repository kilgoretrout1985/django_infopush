====
Push
====

Push is a Django reusable app, what allows to gather push subscriptions and send
web push notifications to browsers (requires SSL-site).

Detailed documentation is in the "docs" directory.

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

4. Configure django_infopush in settings.py (see docs/SETTINGS.rst).

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
   don't want to see push-subscribe browser window.

8. Visit http://127.0.0.1:8000/admin/push/ to check everything is working.

9. CRON setup for pushsend management command (every 5-10 minutes).

10. (OPTOINAL) Run::

    python manage.py test push
    
for basic check of the app. 