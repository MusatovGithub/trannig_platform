from django import template

register = template.Library()


@register.filter
def subtract(value, arg):
    """Sonlarni ayirish uchun Django custom filter"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0  # Agar noto‘g‘ri qiymat bo‘lsa, 0 qaytaradi
