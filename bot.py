import logging
import os
from dataclasses import dataclass
from typing import Dict, Tuple

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

YANDEX_API_URL = "https://api.weather.yandex.ru/v2/forecast"

CONDITION_LABELS = {
    "clear": "ясно",
    "partly-cloudy": "малооблачно",
    "cloudy": "облачно",
    "overcast": "пасмурно",
    "light-rain": "небольшой дождь",
    "rain": "дождь",
    "heavy-rain": "сильный дождь",
    "showers": "ливень",
    "wet-snow": "дождь со снегом",
    "light-snow": "небольшой снег",
    "snow": "снег",
    "snow-showers": "снегопад",
    "hail": "град",
    "thunderstorm": "гроза",
    "thunderstorm-with-rain": "гроза с дождем",
    "thunderstorm-with-hail": "гроза с градом",
}


@dataclass(frozen=True)
class City:
    name: str
    coords: Tuple[float, float]


CITIES: Dict[str, City] = {
    "moscow": City("Москва", (55.7558, 37.6173)),
    "spb": City("Санкт-Петербург", (59.9375, 30.3086)),
    "kazan": City("Казань", (55.7961, 49.1064)),
    "novosibirsk": City("Новосибирск", (55.0287, 82.9061)),
    "ekb": City("Екатеринбург", (56.8389, 60.6057)),
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton(city.name, callback_data=code)]
        for code, city in CITIES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите город, чтобы получить текущую погоду:", reply_markup=reply_markup
    )


async def clicker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clicker_url = os.getenv("CLICKER_URL", "http://localhost:8000")
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть мини-кликер", web_app=WebAppInfo(clicker_url))]]
    )
    await update.message.reply_text(
        "Мини-приложение откроется в отдельном окне.", reply_markup=keyboard
    )
    await update.message.reply_text(f"Если кнопка не открылась, перейдите по ссылке: {clicker_url}")


async def weather_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    city_code = query.data
    city = CITIES.get(city_code)
    if not city:
        await query.edit_message_text("Не удалось найти город. Попробуйте снова.")
        return

    weather = fetch_weather(city)
    if weather is None:
        await query.edit_message_text("Сервис погоды временно недоступен. Попробуйте позже.")
        return

    temp, condition, feels_like = weather
    await query.edit_message_text(
        f"Сейчас в городе {city.name}:\n"
        f"Температура: {temp}°C (ощущается как {feels_like}°C)\n"
        f"Условия: {condition}"
    )


def fetch_weather(city: City) -> Tuple[int, str, int] | None:
    api_key = os.getenv("YANDEX_WEATHER_KEY", "7a5bbc9f-46b4-47ee-8cb9-ac3b09008bb9")
    params = {
        "lat": city.coords[0],
        "lon": city.coords[1],
        "limit": 1,
        "extra": False,
    }
    try:
        response = requests.get(
            YANDEX_API_URL,
            params=params,
            headers={"X-Yandex-API-Key": api_key},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        logging.exception("Failed to fetch weather data")
        return None

    payload = response.json()
    fact = payload.get("fact", {})
    temp = fact.get("temp")
    feels_like = fact.get("feels_like")
    condition_code = fact.get("condition", "clear")
    condition = CONDITION_LABELS.get(condition_code, condition_code)

    if temp is None or feels_like is None:
        return None

    return temp, condition, feels_like


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Please export a valid token.")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clicker", clicker))
    application.add_handler(CallbackQueryHandler(weather_callback))

    application.run_polling()


if __name__ == "__main__":
    main()
