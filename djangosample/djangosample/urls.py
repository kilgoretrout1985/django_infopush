from django.contrib import admin
from django.urls import re_path, include

from django.conf import settings
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page


urlpatterns = [
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^push/', include('push.urls')),
    re_path(r'^service-worker.js$', cache_page(1 if settings.DEBUG else 86400)(TemplateView.as_view(
        template_name="push/service-worker.js",
        content_type='application/javascript; charset='+settings.DEFAULT_CHARSET,
    )), name='service-worker.js'),
]
