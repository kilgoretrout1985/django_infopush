# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.db.models import Sum
from django.utils.translation import ugettext_lazy as _, ungettext

from commonstuff.filters import MyDateListFilterNoFuture, MyDateListFilter

from .models import DigestSubscription, Task
from .forms import TaskAdminForm
from .filters import IsDoneFilter


class BaseSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('endpoint_truncated', 'is_active', 'errors', 'created_at', \
                    'activated_at', 'deactivated_at',)
    list_filter = (
        'is_active',
        ('created_at', MyDateListFilterNoFuture),
        ('activated_at', MyDateListFilterNoFuture),
        ('deactivated_at', MyDateListFilterNoFuture),
    )
    search_fields = ('endpoint', 'ua', 'key', 'auth_secret', 'timezone')
    date_hierarchy = 'created_at'
    list_per_page = 20
    ordering = ('-created_at',)
    has_add_permission = lambda self, request: False
    readonly_fields = ['endpoint', 'key', 'auth_secret', 'errors', 'ua', \
                       'timezone', 'created_at', 'activated_at', \
                       'deactivated_at',]


class DigestSubscriptionAdmin(BaseSubscriptionAdmin):
    pass


class TaskChangeList(ChangeList):
    def get_results(self, request):
        super(TaskChangeList, self).get_results(request)
        totals = self.result_list.aggregate(
            total_views=Sum('views'),
            total_clicks=Sum('clicks'),
            total_closings=Sum('closings')
        )
        try:
            totals['avg_ctr'] = "%0.2f%%" % (totals['total_clicks'] * 100.0 / totals['total_views'])
        except (ZeroDivisionError, TypeError):
            totals['avg_ctr'] = 'n/a'
        try:
            totals['avg_closings'] = "%0.2f%%" % (totals['total_closings'] * 100.0 / totals['total_views'])
        except (ZeroDivisionError, TypeError):
            totals['avg_closings'] = 'n/a'
        self.totals = totals


class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm
    list_display = ('title', 'message', 'is_active', 'has_image', 'has_image2',\
                    'views', 'clicks', 'ctr', 'closings_percent', 'run_at', \
                    'is_done', 'run_for')
    list_filter = (
        'is_active',
        IsDoneFilter,
        ('run_at', MyDateListFilter),
        ('done_at', MyDateListFilterNoFuture),
    )
    search_fields = ('title', 'message', 'url')
    date_hierarchy = 'run_at'
    list_per_page = 20
    list_max_show_all = 3000
    ordering = ('-run_at',)
    readonly_fields = ['started_at', 'done_at',]
    actions = ['activate_tasks', 'deactivate_tasks']
    
    def get_readonly_fields(self, request, obj=None):
        ro = self.readonly_fields[:]
        if obj and obj.started_at:
            ro.insert(0, 'run_at')  # maintain field order
        return ro
    
    def get_changelist(self, request):
        return TaskChangeList
    
    def _activate_deactivate_tasks(self, request, queryset, activate):
        counter = 0
        for task in queryset:
            if task.is_active != activate:
                task.is_active = activate
                task.save()
                counter += 1
        if counter:
            if activate:
                msg = ungettext(
                    'Successfully activated %(count)d task.',
                    'Successfully activated %(count)d tasks.',
                    counter
                ) % {'count': counter}
            else:
                msg = ungettext(
                    'Successfully deactivated %(count)d task.',
                    'Successfully deactivated %(count)d tasks.',
                    counter
                ) % {'count': counter}
            self.message_user(request, msg)
    
    def deactivate_tasks(self, request, queryset):
        self._activate_deactivate_tasks(request, queryset, False)
    deactivate_tasks.short_description = _('Deactivate selected tasks')

    def activate_tasks(self, request, queryset):
        self._activate_deactivate_tasks(request, queryset, True)
    activate_tasks.short_description = _('Activate selected tasks')


admin.site.register(Task, TaskAdmin)
admin.site.register(DigestSubscription, DigestSubscriptionAdmin)
