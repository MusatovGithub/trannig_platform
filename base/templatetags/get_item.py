from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Returns the value of the specified key in the dictionary."""
    return dictionary.get(key)


@register.filter
def isin(value, arg):
    return value in arg
