from django.db import models


class TagsTextChoices(models.TextChoices):
    """Теги для достижений."""

    # # Базовые теги
    # BASIC = "basic", "Базовый"
    # ADVANCED = "advanced", "Продвинутый"
    # PRO = "pro", "Профи"

    # Новые теги согласно требованиям
    WATER_ELEMENT = "water_element", "Водная стихия (базовый уровень)"
    SWIMMING_SKILLS = (
        "swimming_skills",
        "Умею плавать (технический, средний уровень)",
    )
    CHAMPION_PATH = (
        "champion_path",
        "Чемпионский путь (соревнования, личные достижения)",
    )
    TEAM_CAPTAIN = "team_captain", "Капитан команды (лидерские навыки)"
    LAND_CHAMPION = "land_champion", "Сухопутный чемпион (достижения на суше)"
    MEDIA_CHAMPION = "media_champion", "Медиа-чемпион (социальные достижения)"
    CHALLENGE_MASTER = (
        "challenge_master",
        "Челлендж-мастер (командные испытания)",
    )
