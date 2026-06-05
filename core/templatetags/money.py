from django import template

from core.money import format_money_br

register = template.Library()


@register.filter(name='money_br')
def money_br(value):
    return format_money_br(value)
