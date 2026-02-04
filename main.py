import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "7991138339:AAGUvKh4l8VTxNOFLoGEVW1-_m7n8yhg_U0")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "7a5bbc9f-46b4-47ee-8cb9-ac3b09008bb9")
NGROK_URL = os.getenv("NGROK_URL", "https://your-ngrok-url.ngrok-free.app")
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8000

DB_PATH = "solar_farm.db"

logging.basicConfig(level=logging.INFO)


@dataclass
class City:
    name: str
    lat: float
    lon: float


CITIES = [
    City("Москва", 55.7558, 37.6173),
    City("Санкт-Петербург", 59.9343, 30.3351),
    City("Казань", 55.7961, 49.1064),
    City("Новосибирск", 55.0084, 82.9357),
    City("Екатеринбург", 56.8389, 60.6057),
    City("Сочи", 43.6028, 39.7342),
    City("Краснодар", 45.0355, 38.9753),
    City("Владивосток", 43.1155, 131.8855),
    City("Калининград", 54.7104, 20.4522),
    City("Нижний Новгород", 56.2965, 43.9361),
    City("Ростов-на-Дону", 47.2357, 39.7015),
    City("Самара", 53.1959, 50.1008),
    City("Омск", 54.9885, 73.3242),
    City("Уфа", 54.7388, 55.9721),
    City("Пермь", 58.0105, 56.2502),
]


class WeatherStates(StatesGroup):
    waiting_for_city = State()


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    points INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    click_power INTEGER DEFAULT 1,
                    auto_clicker INTEGER DEFAULT 0,
                    farms INTEGER DEFAULT 0,
                    weather_cache TEXT,
                    weather_updated_at TEXT
                )
                """
            )
            await db.commit()

    async def upsert_user(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id)
                VALUES (?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id,),
            )
            await db.commit()

    async def update_progress(self, user_id: int, payload: dict[str, Any]) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, points, level, click_power, auto_clicker, farms)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    points=excluded.points,
                    level=excluded.level,
                    click_power=excluded.click_power,
                    auto_clicker=excluded.auto_clicker,
                    farms=excluded.farms
                """,
                (
                    user_id,
                    int(payload.get("points", 0)),
                    int(payload.get("level", 1)),
                    int(payload.get("click_power", 1)),
                    int(payload.get("auto_clicker", 0)),
                    int(payload.get("farms", 0)),
                ),
            )
            await db.commit()

    async def cache_weather(self, user_id: int, weather: dict[str, Any]) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE users SET weather_cache = ?, weather_updated_at = ?
                WHERE user_id = ?
                """,
                (json.dumps(weather, ensure_ascii=False), datetime.utcnow().isoformat(), user_id),
            )
            await db.commit()


db = Database(DB_PATH)
router = Router()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌤 Погода по городам", callback_data="weather:list:0")],
            [
                InlineKeyboardButton(
                    text="⚡️ Запустить Солнечный Кликер",
                    web_app=WebAppInfo(url=f"{NGROK_URL}/"),
                )
            ],
        ]
    )


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu")]]
    )


def cities_keyboard(page: int, page_size: int = 5) -> InlineKeyboardMarkup:
    start = page * page_size
    end = start + page_size
    rows = []
    for idx, city in enumerate(CITIES[start:end], start=start):
        rows.append([InlineKeyboardButton(text=city.name, callback_data=f"weather:city:{idx}")])

    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"weather:list:{page - 1}"))
    if end < len(CITIES):
        navigation.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"weather:list:{page + 1}"))
    if navigation:
        rows.append(navigation)

    rows.append([InlineKeyboardButton(text="🔍 Найти город", callback_data="weather:search")])
    rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def weather_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ К списку городов", callback_data="weather:list:0")]]
    )


def condition_emoji(condition: str) -> str:
    mapping = {
        "clear": "☀️",
        "partly-cloudy": "⛅️",
        "cloudy": "☁️",
        "overcast": "🌥",
        "drizzle": "🌦",
        "light-rain": "🌧",
        "rain": "🌧",
        "moderate-rain": "🌧",
        "heavy-rain": "🌧",
        "continuous-heavy-rain": "⛈",
        "showers": "⛈",
        "wet-snow": "🌨",
        "light-snow": "❄️",
        "snow": "❄️",
        "snow-showers": "❄️",
        "hail": "🌨",
        "thunderstorm": "⛈",
        "thunderstorm-with-rain": "⛈",
        "thunderstorm-with-hail": "⛈",
        "fog": "🌫",
    }
    return mapping.get(condition, "🌡")


def wind_direction_text(code: str) -> str:
    mapping = {
        "nw": "северо-западный",
        "n": "северный",
        "ne": "северо-восточный",
        "e": "восточный",
        "se": "юго-восточный",
        "s": "южный",
        "sw": "юго-западный",
        "w": "западный",
        "c": "штиль",
    }
    return mapping.get(code, "—")


async def fetch_weather(lat: float, lon: float) -> dict[str, Any]:
    url = "https://api.weather.yandex.ru/v2/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "lang": "ru_RU",
        "limit": 3,
        "hours": False,
        "extra": True,
    }
    headers = {"X-Yandex-API-Key": YANDEX_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=20) as response:
            response.raise_for_status()
            return await response.json()


async def geocode_city(city_name: str) -> City | None:
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={"User-Agent": "SolarFarmBot"},
            timeout=10,
        ) as response:
            response.raise_for_status()
            data = await response.json()
    if not data:
        return None
    item = data[0]
    return City(item.get("display_name", city_name), float(item["lat"]), float(item["lon"]))


def format_weather(city: str, data: dict[str, Any]) -> str:
    fact = data["fact"]
    forecast = data["forecast"]
    emoji = condition_emoji(fact.get("condition"))
    parts = []
    for day in data.get("forecasts", [])[:3]:
        date = day.get("date")
        parts.append(f"<b>📅 {date}</b>")
        for part_name, title in (
            ("morning", "🌅 Утро"),
            ("day", "🌞 День"),
            ("evening", "🌆 Вечер"),
            ("night", "🌙 Ночь"),
        ):
            part = day.get("parts", {}).get(part_name)
            if not part:
                continue
            part_emoji = condition_emoji(part.get("condition"))
            temp = part.get("temp_avg")
            prec = part.get("prec_prob")
            parts.append(
                f"{title}: {part_emoji} {temp}°C, осадки {prec}%"
            )
        parts.append("")

    forecast_text = "\n".join(parts)

    return (
        f"<b>☀️ Погода в городе {city}</b>\n\n"
        f"<b>Сейчас:</b> {emoji} <b>{fact.get('temp')}°C</b>\n"
        f"Ощущается как: <b>{fact.get('feels_like')}°C</b>\n"
        f"Состояние: <i>{fact.get('condition')}</i>\n\n"
        f"<b>Детали:</b>\n"
        f"💧 Влажность: <b>{fact.get('humidity')}%</b>\n"
        f"📍 Давление: <b>{fact.get('pressure_mm')} мм рт. ст.</b>\n"
        f"🌬 Скорость ветра: <b>{fact.get('wind_speed')} м/с</b>\n"
        f"🧭 Направление: <b>{wind_direction_text(fact.get('wind_dir'))}</b>\n"
        f"🕶 УФ-индекс: <b>{fact.get('uv_index', '—')}</b>\n"
        f"🌅 Восход: <b>{forecast.get('sunrise', '—')}</b>\n"
        f"🌇 Закат: <b>{forecast.get('sunset', '—')}</b>\n\n"
        f"<b>Прогноз на 3 дня:</b>\n{forecast_text}"
    )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await db.upsert_user(message.from_user.id)
    greeting = (
        "<b>Привет!</b> Я бот <b>\"Солнечная Ферма\"</b> ☀️\n"
        "Покажу подробную погоду и открою солнечный кликер!"
    )
    await message.answer(greeting, reply_markup=main_menu(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "menu")
async def menu_handler(callback) -> None:
    await callback.message.edit_text(
        "<b>Главное меню</b>", reply_markup=main_menu(), parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data.startswith("weather:list"))
async def weather_list(callback) -> None:
    page = int(callback.data.split(":")[-1])
    await callback.message.edit_text(
        "<b>Выберите город:</b>",
        reply_markup=cities_keyboard(page),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "weather:search")
async def weather_search(callback, state: FSMContext) -> None:
    await state.set_state(WeatherStates.waiting_for_city)
    await callback.message.edit_text(
        "Введите название города для поиска:",
        reply_markup=back_to_menu(),
    )
    await callback.answer()


@router.message(WeatherStates.waiting_for_city)
async def process_city_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db.upsert_user(message.from_user.id)
    city_name = message.text.strip()
    await message.answer("Ищу город, секунду...")
    city = await geocode_city(city_name)
    if not city:
        await message.answer(
            "Не удалось найти город. Попробуйте еще раз.", reply_markup=back_to_menu()
        )
        return
    data = await fetch_weather(city.lat, city.lon)
    await db.cache_weather(message.from_user.id, data)
    await message.answer(
        format_weather(city.name, data),
        parse_mode=ParseMode.HTML,
        reply_markup=weather_back_keyboard(),
    )


@router.callback_query(F.data.startswith("weather:city"))
async def weather_city(callback) -> None:
    idx = int(callback.data.split(":")[-1])
    city = CITIES[idx]
    await db.upsert_user(callback.from_user.id)
    await callback.message.edit_text("Запрашиваю погоду...")
    data = await fetch_weather(city.lat, city.lon)
    await db.cache_weather(callback.from_user.id, data)
    await callback.message.edit_text(
        format_weather(city.name, data),
        parse_mode=ParseMode.HTML,
        reply_markup=weather_back_keyboard(),
    )
    await callback.answer()


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message) -> None:
    await db.upsert_user(message.from_user.id)
    try:
        payload = json.loads(message.web_app_data.data)
    except json.JSONDecodeError:
        await message.answer("Не удалось прочитать данные из приложения.")
        return
    await db.update_progress(message.from_user.id, payload)
    await message.answer("✅ Прогресс сохранен!")


async def api_progress(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)
    user_id = int(payload.get("user_id", 0))
    if not user_id:
        return web.json_response({"ok": False, "error": "user_id required"}, status=400)
    await db.update_progress(user_id, payload)
    return web.json_response({"ok": True})


async def start_web_server() -> web.AppRunner:
    app = web.Application(middlewares=[ngrok_header_middleware])
    app.router.add_static("/", path="mini_app", show_index=True)
    app.router.add_post("/api/progress", api_progress)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logging.info("Mini App server started on %s:%s", WEBAPP_HOST, WEBAPP_PORT)
    return runner


@web.middleware
async def ngrok_header_middleware(request: web.Request, handler):
    response = await handler(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


async def main() -> None:
    await db.init()
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    runner = await start_web_server()
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
