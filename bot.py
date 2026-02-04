import logging
import os
from dataclasses import dataclass
from typing import Dict, Tuple

import requests
from dotenv import load_dotenv
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
    region: str
    coords: Tuple[float, float]
    description: str


CITIES: Dict[str, City] = {
    "moscow": City("Москва", "Центральная Россия", (55.7558, 37.6173), "Столица России."),
    "spb": City(
        "Санкт-Петербург",
        "Северо-Запад",
        (59.9375, 30.3086),
        "Город на Неве и культурная столица.",
    ),
    "kazan": City("Казань", "Поволжье", (55.7961, 49.1064), "Столица Татарстана."),
    "novosibirsk": City(
        "Новосибирск",
        "Сибирь",
        (55.0287, 82.9061),
        "Крупнейший город Сибири.",
    ),
    "ekb": City(
        "Екатеринбург",
        "Урал",
        (56.8389, 60.6057),
        "Столица Урала.",
    ),
    "sochi": City("Сочи", "Черноморское побережье", (43.6028, 39.7342), "Курортный город."),
    "kaliningrad": City(
        "Калининград",
        "Балтийский регион",
        (54.7104, 20.4522),
        "Самая западная область РФ.",
    ),
    "vladivostok": City(
        "Владивосток",
        "Дальний Восток",
        (43.1155, 131.8855),
        "Город у Японского моря.",
    ),
    "krasnoyarsk": City(
        "Красноярск",
        "Сибирь",
        (56.0153, 92.8932),
        "Город на берегу Енисея.",
    ),
    "rostov": City(
        "Ростов-на-Дону",
        "Юг России",
        (47.2357, 39.7015),
        "Южные ворота России.",
    ),
    "ufa": City("Уфа", "Башкортостан", (54.7388, 55.9721), "Столица Башкирии."),
}

BACK_TO_CITIES = "back_to_cities"


def build_city_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(city.name, callback_data=code)]
        for code, city in CITIES.items()
    ]
    keyboard.append(
        [InlineKeyboardButton("Мини-апп: солнечный кликер ☀️", web_app=WebAppInfo(get_clicker_url()))]
    )
    return InlineKeyboardMarkup(keyboard)


def get_clicker_url() -> str:
    return os.getenv("CLICKER_URL", "http://localhost:8000")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Выберите город, чтобы получить текущую погоду:",
        reply_markup=build_city_keyboard(),
    )


async def clicker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clicker_url = get_clicker_url()
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть мини-кликер", web_app=WebAppInfo(clicker_url))]]
    )
    await update.message.reply_text(
        "Мини-приложение откроется прямо внутри Telegram.", reply_markup=keyboard
    )
    await update.message.reply_text(f"Если кнопка не открылась, перейдите по ссылке: {clicker_url}")


async def weather_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    city_code = query.data
    if city_code == BACK_TO_CITIES:
        await query.edit_message_text(
            "Выберите город, чтобы получить текущую погоду:",
            reply_markup=build_city_keyboard(),
        )
        return

    city = CITIES.get(city_code)
    if not city:
        await query.edit_message_text("Не удалось найти город. Попробуйте снова.")
        return

    weather = fetch_weather(city)
    if weather is None:
        await query.edit_message_text("Сервис погоды временно недоступен. Попробуйте позже.")
        return

    temp, condition, feels_like, humidity, wind_speed = weather
    reply_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Вернуться к списку городов", callback_data=BACK_TO_CITIES)],
            [InlineKeyboardButton("Мини-апп: солнечный кликер ☀️", web_app=WebAppInfo(get_clicker_url()))],
        ]
    )
    await query.edit_message_text(
        f"Сейчас в городе {city.name} ({city.region}):\n"
        f"Температура: {temp}°C (ощущается как {feels_like}°C)\n"
        f"Условия: {condition}\n"
        f"Влажность: {humidity}%\n"
        f"Ветер: {wind_speed} м/с\n"
        f"Описание города: {city.description}\n"
        f"Координаты: {city.coords[0]}, {city.coords[1]}",
        reply_markup=reply_markup,
    )


def fetch_weather(city: City) -> Tuple[int, str, int, int, float] | None:
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
    humidity = fact.get("humidity")
    wind_speed = fact.get("wind_speed")

    if temp is None or feels_like is None or humidity is None or wind_speed is None:
        return None

    return temp, condition, feels_like, humidity, wind_speed


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "7991138339:AAGUvKh4l8VTxNOFLoGEVW1-_m7n8yhg_U0")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clicker", clicker))
    application.add_handler(CallbackQueryHandler(weather_callback))

    application.run_polling()


if __name__ == "__main__":
    main()
