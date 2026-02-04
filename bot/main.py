import asyncio
import os
from dataclasses import dataclass
from typing import Any

import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

CITY_PAGE_SIZE = 10
POPULAR_CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Новосибирск",
    "Екатеринбург",
    "Сочи",
    "Краснодар",
    "Владивосток",
    "Калининград",
    "Нижний Новгород",
    "Ростов-на-Дону",
    "Самара",
    "Уфа",
    "Пермь",
    "Красноярск",
]


class WeatherSearch(StatesGroup):
    waiting_for_city = State()


@dataclass
class WeatherConfig:
    yandex_api_key: str


async def fetch_json(session: aiohttp.ClientSession, url: str, *, headers: dict[str, str] | None = None) -> Any:
    async with session.get(url, headers=headers) as response:
        response.raise_for_status()
        return await response.json()


async def get_city_coordinates(session: aiohttp.ClientSession, city: str) -> tuple[float, float] | None:
    url = "https://nominatim.openstreetmap.org/search"
    params = f"?format=json&q={city}&limit=1"
    data = await fetch_json(
        session,
        f"{url}{params}",
        headers={"User-Agent": "SolarFarmBot/1.0"},
    )
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


async def get_weather(session: aiohttp.ClientSession, api_key: str, lat: float, lon: float) -> dict[str, Any]:
    url = f"https://api.weather.yandex.ru/v2/forecast?lat={lat}&lon={lon}&limit=4&hours=false"
    headers = {"X-Yandex-API-Key": api_key}
    return await fetch_json(session, url, headers=headers)


def build_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="☀️ Погода по городам", callback_data="weather_menu"),
    )
    builder.row(
        InlineKeyboardButton(
            text="⚡️ Запустить Солнечный Кликер",
            web_app=WebAppInfo(url=os.getenv("MINI_APP_URL", "http://78.140.243.128")),
        )
    )
    return builder.as_markup()


def build_city_page(page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * CITY_PAGE_SIZE
    end = start + CITY_PAGE_SIZE
    for city in POPULAR_CITIES[start:end]:
        builder.row(InlineKeyboardButton(text=city, callback_data=f"city:{city}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cities:{page - 1}"))
    if end < len(POPULAR_CITIES):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"cities:{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔍 Найти город", callback_data="city_search"))
    builder.row(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_menu"))
    return builder.as_markup()


def format_weather(city: str, data: dict[str, Any]) -> str:
    fact = data.get("fact", {})
    forecasts = data.get("forecasts", [])[:4]

    lines = [f"🌤 Погода для города {city}"]
    if fact:
        lines.append(
            "\nСейчас: "
            f"{fact.get('temp', '—')}°C, ощущается как {fact.get('feels_like', '—')}°C, "
            f"{fact.get('condition', 'без данных')}"
        )

    lines.append("\nПрогноз на 3 дня:")
    for forecast in forecasts[1:4]:
        day = forecast.get("date", "—")
        parts = forecast.get("parts", {}).get("day", {})
        temp_min = parts.get("temp_min", "—")
        temp_max = parts.get("temp_max", "—")
        condition = parts.get("condition", "—")
        lines.append(f"• {day}: {temp_min}…{temp_max}°C, {condition}")

    return "\n".join(lines)


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    text = (
        "Привет! Я бот проекта «Солнечная Ферма».\n\n"
        "Выбирай действие ниже:"
    )
    await message.answer(text, reply_markup=build_main_menu())


@router.callback_query(F.data == "weather_menu")
async def weather_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите город из списка или воспользуйтесь поиском:",
        reply_markup=build_city_page(0),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cities:"))
async def paginate_cities(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=build_city_page(page))
    await callback.answer()


@router.callback_query(F.data.startswith("city:"))
async def city_selected(callback: CallbackQuery, state: FSMContext, config: WeatherConfig) -> None:
    city = callback.data.split(":", 1)[1]
    await state.clear()
    await callback.answer("Запрашиваю погоду...")
    async with aiohttp.ClientSession() as session:
        coords = await get_city_coordinates(session, city)
        if not coords:
            await callback.message.answer("Не удалось найти координаты города. Попробуйте поиск.")
            return
        weather = await get_weather(session, config.yandex_api_key, coords[0], coords[1])
    await callback.message.answer(format_weather(city, weather), reply_markup=build_city_page(0))


@router.callback_query(F.data == "city_search")
async def city_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WeatherSearch.waiting_for_city)
    await callback.message.answer("Введите название города:")
    await callback.answer()


@router.message(WeatherSearch.waiting_for_city)
async def handle_city_input(message: Message, state: FSMContext, config: WeatherConfig) -> None:
    city = message.text.strip()
    await state.clear()
    async with aiohttp.ClientSession() as session:
        coords = await get_city_coordinates(session, city)
        if not coords:
            await message.answer("Не удалось найти город. Попробуйте снова или выберите из списка.")
            return
        weather = await get_weather(session, config.yandex_api_key, coords[0], coords[1])
    await message.answer(format_weather(city, weather), reply_markup=build_city_page(0))


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=build_main_menu(),
    )
    await callback.answer()


async def main() -> None:
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")
    yandex_api_key = os.getenv("YANDEX_API_KEY")

    if not bot_token or not yandex_api_key:
        raise RuntimeError("BOT_TOKEN и YANDEX_API_KEY должны быть заданы в окружении.")

    config = WeatherConfig(yandex_api_key=yandex_api_key)
    bot = Bot(bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    await dispatcher.start_polling(bot, config=config)


if __name__ == "__main__":
    asyncio.run(main())
