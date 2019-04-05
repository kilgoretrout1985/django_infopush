# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

from django import template

from push import settings

register = template.Library()


@register.simple_tag
def push_settings(name):
    return vars(settings)[name]
