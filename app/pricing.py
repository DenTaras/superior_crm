"""Таблица цен на абонементы."""

# Матрица цен: время → формат → размер пакета → цена (руб, весь пакет)
PRICING = {
    "УТРО": {
        "VIP":   {4: 15000, 8: 28000, 12: 39000},
        "Double": {4: 12000, 8: 22000, 12: 30000},
        "Group": {4: 10000, 8: 17000, 12: 24000},
    },
    "ДЕНЬ": {
        "VIP":   {4: 12000, 8: 23080, 12: 32000},
        "Double": {4: 10000, 8: 17000, 12: 24000},
        "Group": {4: 8000, 8: 14000, 12: 19000},
    },
    "ВЕЧЕР": {
        "VIP":   {4: 20000, 8: 37000, 12: 50000},
        "Double": {4: 15000, 8: 28000, 12: 39000},
        "Group": {4: 12000, 8: 23000, 12: 32000},
    },
}

TIME_SLOTS = list(PRICING.keys())
FORMATS = list(PRICING["УТРО"].keys())
PACKAGE_SIZES = [4, 8, 12]


def get_price(time_slot: str, format_name: str, package_size: int) -> int | None:
    """Получить цену для комбинации или None."""
    return PRICING.get(time_slot, {}).get(format_name, {}).get(package_size)


def slot_time_slot(dt) -> str:
    """Определить временной слот (УТРО/ДЕНЬ/ВЕЧЕР) по времени начала."""
    h = dt.hour
    if 8 <= h < 12:
        return "УТРО"
    if 12 <= h < 17:
        return "ДЕНЬ"
    return "ВЕЧЕР"


def format_from_capacity(capacity: int) -> str:
    """Определить формат (VIP/Double/Group) по вместимости слота.

    capacity=1 → VIP (персональная тренировка)
    capacity=2 → Double (парная)
    capacity>=3 → Group (групповая)
    """
    if capacity <= 1:
        return "VIP"
    if capacity == 2:
        return "Double"
    return "Group"


def get_all_options() -> list[dict]:
    """Все возможные комбинации для формы."""
    options = []
    for time_slot in TIME_SLOTS:
        for fmt in FORMATS:
            for size in PACKAGE_SIZES:
                price = get_price(time_slot, fmt, size)
                options.append({
                    "time_slot": time_slot,
                    "format": fmt,
                    "package_size": size,
                    "price": price,
                    "label": f"{fmt} {time_slot} {size} — {price} руб",
                })
    return options
