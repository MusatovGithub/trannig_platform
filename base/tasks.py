from celery import shared_task
from django.core.mail import EmailMultiAlternatives


@shared_task
def send_email_to_user(
    subject,
    message,
    from_email,
    recipient_list,
    html_message=None,
    extra_headers=None,
):
    """Отправка письма пользователю."""
    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=from_email,
        to=recipient_list,
        headers=extra_headers or {},
    )
    if html_message:
        email.attach_alternative(html_message, "text/html")
    email.send()
