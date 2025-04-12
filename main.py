import logging
import asyncio
import re
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import Command
from aiogram import F
from aiogram.utils.keyboard import ReplyKeyboardBuilder

API_TOKEN = '8132728411:AAGxK5QFdkBaUHRjs-Ip3XkGncyTbHl1bco'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

accounts = {}
archives = {}
pending_deletion = {}

def load_data():
    global accounts, archives
    try:
        with open("accounts.json", "r", encoding="utf-8") as f:
            accounts.update(json.load(f))
    except: pass
    try:
        with open("archives.json", "r", encoding="utf-8") as f:
            archives.update(json.load(f))
    except: pass

def save_data():
    with open("accounts.json", "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)
    with open("archives.json", "w", encoding="utf-8") as f:
        json.dump(archives, f, ensure_ascii=False, indent=2)

def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Добавить")
    kb.button(text="📄 Реквизиты")
    kb.button(text="📦 Архив")
    kb.button(text="❌ Удалить")
    return kb.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Выбери действие:", reply_markup=main_menu())

@dp.message()
async def handle_all(message: Message):
    user_id = message.from_user.id
    text = message.text or message.caption or ""

    if text.startswith("➕"):
        await message.answer("Введи данные в формате:\n\nФИО\nТелефон\nКарта\n\nДанные для IBAN и т.д.\n\nЛимит")
        return

    if text.startswith("📄"):
        if not accounts:
            await message.answer("Пока нет активных реквизитов.")
            return
        response = ""
        for name, acc in accounts.items():
            response += f"<b>{name}</b>\nЛимит: {acc['остаток']} грн\n{acc['реквизиты']}\n"
            response += "______________________________________\n\n"
        await message.answer(response.strip(), parse_mode=ParseMode.HTML)
        return

    if text.startswith("📦"):
        if not archives:
            await message.answer("Архив пуст.")
            return
        response = "📦 Архивные реквизиты:\n\n"
        for name, acc in archives.items():
            response += f"<b>{name}</b>\n{acc['реквизиты']}\n\n"
            response += "______________________________________\n\n"
        await message.answer(response.strip(), parse_mode=ParseMode.HTML)
        return

    if text.startswith("❌") or text.startswith("/удалить"):
        parts = text.strip().split(maxsplit=1)
        if len(parts) == 2:
            name = parts[1]
            if name in accounts:
                pending_deletion[message.from_user.id] = name
                await message.answer("📎 Отправь выписку (файл или текст), чтобы завершить удаление.")
            else:
                await message.answer("Такого аккаунта нет.")
        else:
            await message.answer("Пример: /удалить Заєць")
        return

    if "⏳" in text:
        try:
            amount_match = re.search(r"⏳\s*([\d.]+)", text)
            amount = float(amount_match.group(1)) if amount_match else None
            all_possible = re.findall(r"\d{16}|\d{4}\s\d{4}\s\d{4}\s\d{4}", text)
            candidates = [c.replace(" ", "") for c in all_possible if c.replace(" ", "").isdigit()]
            card_number = next((c for c in candidates if c.startswith(('4', '5')) and len(c) == 16), None)
            if not amount or not card_number:
                await message.answer("❌ Не найдена сумма или номер карты.")
                return
            for name, acc in accounts.items():
                all_cards_raw = re.findall(r"\d{16}|\d{4} \d{4} \d{4} \d{4}", acc["реквизиты"])
                all_cards_cleaned = [c.replace(" ", "") for c in all_cards_raw if c.replace(" ", "").isdigit()]
                filtered_cards = [c for c in all_cards_cleaned if len(c) == 16 and c.startswith(("4", "5"))]
                print(f"🔍 Проверка карты {card_number} среди: {filtered_cards} ({name})")
                if card_number in filtered_cards:
                    accounts[name]["остаток"] -= amount
                    save_data()
                    await message.answer(f"✅ {amount} грн вычтено с карты {card_number} ({name}). Новый лимит: {accounts[name]['остаток']} грн.")
                    return
            await message.answer("ℹ️ Карта не найдена, но сообщение обработано.")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await message.answer("❌ Ошибка при распознавании.")
        return

    if user_id in pending_deletion:
        name = pending_deletion.pop(user_id)
        if name in accounts:
            archives[name] = accounts.pop(name)
            save_data()
            await message.answer(f"✅ Реквизиты {name} удалены и добавлены в архив.")
        return

    lines = text.split("\n")
    if len(lines) >= 6:
        try:
            name = lines[0].strip()
            phone = lines[1].strip()
            card = lines[2].strip()
            limit = int(lines[-1].strip())
            block = "\n".join(lines[3:-1]).strip()
            requisites = f"{name}\n{phone}\n{card}\n\n{block}"
            accounts[name] = {
                "лимит": limit,
                "остаток": limit,
                "реквизиты": requisites
            }
            save_data()
            await message.answer(f"✅ Добавлен {name} с лимитом {limit}")
        except:
            await message.answer("⚠️ Ошибка при добавлении. Проверь формат.")
        return

    if text.startswith("/вычесть"):
        try:
            _, name, amount = text.split()
            amount = float(amount)
            if name in accounts:
                accounts[name]["остаток"] -= amount
                save_data()
                await message.answer(f"💸 У {name} теперь {accounts[name]['остаток']} грн.")
            else:
                await message.answer("Такого имени нет.")
        except:
            await message.answer("Ошибка. Пример: /вычесть Заєць 30000")

@dp.message(F.document)
async def handle_file(message: Message):
    user_id = message.from_user.id
    if user_id in pending_deletion:
        name = pending_deletion.pop(user_id)
        if name in accounts:
            archives[name] = accounts.pop(name)
            save_data()
            await message.answer(f"📁 Выписка получена. {name} удалён и добавлен в архив.")

async def main():
    load_data()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
