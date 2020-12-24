from django import template

from push import settings

register = template.Library()


@register.simple_tag
def push_settings(name):
    return vars(settings)[name]
