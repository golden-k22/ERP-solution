import datetime
from django import template

register = template.Library()

@register.simple_tag
def addDays(start_date, days):
   newDate = start_date + datetime.timedelta(days=days)
   return newDate


@register.simple_tag
def resolve(list, index):
    try:
        return list[index]
    except:
        return None
@register.simple_tag
def next_alpha(s):
    return chr((ord(s.upper()) + 1 - 65) % 26 + 65)

@register.filter(name='get_range')
def get_range(number):
    if number<10:
        return range(10)
    return range(number)