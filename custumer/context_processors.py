from django.urls import get_resolver


def get_resolved_urls(request):
    urls = []
    resolver = get_resolver()  # Barcha URLlarni olish

    def recursive_urls(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(
                pattern, "url_patterns"
            ):  # Agar `include` bo‘lsa, ichiga kirish
                recursive_urls(
                    pattern.url_patterns, prefix + str(pattern.pattern)
                )
            else:
                full_url = (
                    "/" + prefix + str(pattern.pattern)
                )  # URL boshiga `/` qo‘shish
                urls.append(
                    full_url.replace("//", "/")
                )  # Qo‘shaloq `/` bo‘lsa, bitta qilib qo‘yish

    recursive_urls(resolver.url_patterns)
    return {"resolved_urls": urls}
