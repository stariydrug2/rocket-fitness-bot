# Rocket Fitness Bot

Telegram-бот для фитнес-зала «Ракета» на `aiogram 3`, `SQLite` и `APScheduler`.

## Что умеет

- запись на тренировку на 1 месяц вперёд
- выбор услуги, даты и времени
- опциональная проверка подписки на канал перед записью
- сбор имени, телефона и цели тренировки
- одна активная запись на пользователя
- отмена своей записи
- уведомления админу
- опциональная публикация в отдельный канал расписания
- автонапоминание за 24 часа
- восстановление напоминаний после перезапуска
- админ-панель для управления слотами и записями

## Установка

```bash
python -m venv .venv
source .venv/bin/activate  # Linux / macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Переменные окружения

Проект читает настройки через `python-dotenv`, но для Bothost удобнее задавать их прямо в панели.
Локально можно скопировать `.env.example` в `.env` и заполнить значения.

Обязательные переменные:

```text
BOT_TOKEN=...
ADMIN_IDS=907849057
```

Необязательные переменные:

```text
CHANNEL_ID=-100...
CHANNEL_LINK=https://t.me/...
SCHEDULE_CHANNEL_ID=-100...
DB_PATH=rocket_fitness.db
TIMEZONE=Europe/Amsterdam
BOOKING_HORIZON_DAYS=31
REQUIRE_SUBSCRIPTION_FOR_BOOKING=false
BRAND_NAME=Ракета
```

Если `REQUIRE_SUBSCRIPTION_FOR_BOOKING=true`, нужно обязательно указать `CHANNEL_ID` и `CHANNEL_LINK`.
Если `SCHEDULE_CHANNEL_ID` пустой, публикация расписания в канал отключается.

## Запуск

```bash
python bot.py
```

## Деплой в Bothost

- регион: **Нидерланды (Амстердам)**
- главный файл: **bot.py**
- домен: **не нужен**
- переменные окружения: добавь их в панели Bothost

## Структура проекта

```text
bot.py
config.py
requirements.txt
.env.example
app/
  database/
    db.py
  handlers/
    admin.py
    user.py
  keyboards/
    admin.py
    calendar.py
    common.py
  services/
    booking_service.py
    reminders.py
    utils.py
  states.py
```
