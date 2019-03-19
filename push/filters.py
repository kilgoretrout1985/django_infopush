# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

from django.utils.translation import ugettext as _

from commonstuff.filters import MyNullNotNullFilter


class IsDoneFilter(MyNullNotNullFilter):
    """
    Model field stores datetime when push task has been done, but in admin
    this filter reduces options to not sent (IS NULL) or already sent (NOT NULL).
    """

    title = _('already sent?')
    parameter_name = 'done_at'
