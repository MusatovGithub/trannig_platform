from django import template

register = template.Library()


@register.filter
def is_available_for_customer(product, customer):
    """
    Template filter для проверки доступности товара для клиента.
    """
    return product.is_available_for_customer(customer)
