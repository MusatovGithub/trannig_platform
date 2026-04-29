def prettify_email_address(email: str) -> str:
    """
    Возвращает email с декодированным IDNA-доменом (punycode -> Unicode).
    Если декодирование не удалось, возвращает исходное значение.
    """
    if not email or "@" not in email:
        return email

    local_part, domain = email.rsplit("@", 1)
    try:
        decoded_domain = domain.encode("ascii").decode("idna")
    except (UnicodeError, ValueError):
        return email

    return f"{local_part}@{decoded_domain}"
