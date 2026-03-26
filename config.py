from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


class ConfigError(ValueError):
    pass


def _parse_admin_ids(raw_value: str) -> List[int]:
    values = [item.strip() for item in (raw_value or "").split(",") if item.strip()]
    if not values:
        raise ConfigError("ADMIN_IDS не задан. Укажите хотя бы один Telegram ID администратора")

    result: list[int] = []
    for item in values:
        try:
            result.append(int(item))
        except ValueError as exc:
            raise ConfigError(f"Некорректный ADMIN_IDS: {item!r}") from exc
    return result


def _get_required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ConfigError(f"Обязательная переменная {name} не задана")
    return value


def _get_optional_int(name: str, default: int = 0) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Переменная {name} должна быть целым числом") from exc


@dataclass(slots=True)
class ServiceItem:
    code: str
    title: str
    price: str
    description: str


@dataclass(slots=True)
class Settings:
    bot_token: str = field(default_factory=lambda: _get_required("BOT_TOKEN"))
    admin_ids: List[int] = field(default_factory=lambda: _parse_admin_ids(os.getenv("ADMIN_IDS", "")))
    channel_id: int = field(default_factory=lambda: _get_optional_int("CHANNEL_ID", 0))
    channel_link: str = field(default_factory=lambda: (os.getenv("CHANNEL_LINK") or "").strip())
    schedule_channel_id: int = field(default_factory=lambda: _get_optional_int("SCHEDULE_CHANNEL_ID", 0))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "rocket_fitness.db"))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Europe/Amsterdam"))
    booking_horizon_days: int = field(default_factory=lambda: max(1, _get_optional_int("BOOKING_HORIZON_DAYS", 31)))
    require_subscription_for_booking: bool = field(
        default_factory=lambda: (os.getenv("REQUIRE_SUBSCRIPTION_FOR_BOOKING", "false").strip().lower() == "true")
    )
    brand_name: str = field(default_factory=lambda: os.getenv("BRAND_NAME", "Ракета"))

    about_text: str = (
        "<b>Фитнес-зал «Ракета»</b>\n\n"
        "Современный зал для тех, кто хочет тренироваться системно и с результатом. "
        "Проводим персональные тренировки, пробные занятия и стартовые консультации.\n\n"
        "<b>Адрес:</b> ул. Спортивная, 7\n"
        "<b>График:</b> ежедневно с 08:00 до 22:00\n"
        "<b>Форматы:</b> силовые, снижение веса, набор массы, мобильность, базовая подготовка."
    )
    reviews_text: str = (
        "<b>Отзывы и соцсети</b>\n\n"
        "Посмотрите отзывы клиентов, фотографии зала и актуальные новости по кнопкам ниже."
    )
    prices_text: str = (
        "<b>Услуги и цены</b>\n\n"
        "Пробная тренировка — 1000₽\n"
        "Персональная тренировка — 2500₽\n"
        "Консультация с тренером — 1500₽\n"
        "Абонементы и пакеты тренировок — по запросу у администратора"
    )
    welcome_text: str = (
        "<b>Добро пожаловать в фитнес-зал «Ракета» 🚀</b>\n\n"
        "Через этого бота можно записаться на тренировку, посмотреть цены, "
        "узнать информацию о зале и быстро отменить запись."
    )
    reminder_text_template: str = (
        "<b>Напоминание о тренировке</b>\n\n"
        "Вы записаны в фитнес-зал «Ракета» на <b>{date}</b> в <b>{time}</b>.\n"
        "Услуга: <b>{service}</b>\n\n"
        "Ждём вас 🚀"
    )

    services: List[ServiceItem] = field(
        default_factory=lambda: [
            ServiceItem(
                code="trial",
                title="Пробная тренировка",
                price="1000₽",
                description="Первое знакомство с залом и тренером.",
            ),
            ServiceItem(
                code="personal",
                title="Персональная тренировка",
                price="2500₽",
                description="Индивидуальная тренировка под ваши цели.",
            ),
            ServiceItem(
                code="consultation",
                title="Консультация",
                price="1500₽",
                description="Разбор целей, состояния и рекомендаций по старту.",
            ),
        ]
    )

    goals: List[str] = field(
        default_factory=lambda: [
            "Похудение",
            "Набор массы",
            "Поддержание формы",
            "Мобильность / растяжка",
            "Другое",
        ]
    )

    review_links: dict = field(
        default_factory=lambda: {
            "Отзывы клиентов": "https://t.me/rocket_fitness_reviews",
            "Фото зала": "https://t.me/rocket_fitness_gallery",
            "Telegram-канал": "https://t.me/rocket_fitness_news",
        }
    )

    def __post_init__(self) -> None:
        if self.require_subscription_for_booking and (not self.channel_id or not self.channel_link):
            raise ConfigError(
                "Для проверки подписки нужно указать CHANNEL_ID и CHANNEL_LINK, "
                "либо отключить REQUIRE_SUBSCRIPTION_FOR_BOOKING"
            )


settings = Settings()
