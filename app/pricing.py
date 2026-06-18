"""Таблица цен на абонементы."""

# Матрица цен: время → формат → размер пакета → цена (руб, весь пакет)
PRICING = {
    "УТРО": {
        "VIP":   {1: 5200, 4: 15600, 8: 28600, 12: 39000},
        "Double": {1: 4000, 4: 12000, 8: 22000, 12: 30000},
        "Group": {1: 3200, 4: 9600, 8: 17600, 12: 24000},
    },
    "ДЕНЬ": {
        "VIP":   {1: 4160, 4: 12480, 8: 22880, 12: 31200},
        "Double": {1: 3200, 4: 9600, 8: 17600, 12: 24000},
        "Group": {1: 2560, 4: 7680, 8: 14080, 12: 19200},
    },
    "ВЕЧЕР": {
        "VIP":   {1: 6760, 4: 20280, 8: 37180, 12: 50700},
        "Double": {1: 5200, 4: 15600, 8: 28600, 12: 39000},
        "Group": {1: 4160, 4: 12480, 8: 22880, 12: 31200},
    },
}

TIME_SLOTS = list(PRICING.keys())
FORMATS = list(PRICING["УТРО"].keys())
PACKAGE_SIZES = [1, 4, 8, 12]


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
