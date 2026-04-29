from django import template

register = template.Library()


@register.filter
def has_group(user, group_name):
    """Returns True if the user has the specified group."""
    return user.groups.filter(name=group_name).exists()


@register.simple_tag(takes_context=True)
def is_admin(context):
    user = context["request"].user
    return user.is_authenticated and user.groups.filter(name="admin").exists()


@register.simple_tag(takes_context=True)
def is_client(context):
    user = context["request"].user
    return user.is_authenticated and user.groups.filter(name="client").exists()
