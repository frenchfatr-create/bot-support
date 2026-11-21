from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import OWNER_IDS, ADMIN_IDS
from database.queries import get_stats, add_admin, remove_admin, set_banned, get_database_admin_ids
from database.queries import get_admin_queue, save_admin_card
from keyboards.admin import new_ticket_card
from html import escape

router = Router()

async def is_admin(uid):
    return uid in OWNER_IDS or uid in ADMIN_IDS or uid in await get_database_admin_ids()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    stats = await get_stats()
    await message.answer(
        "<b>Панель поддержки</b>\n"
        f"Новые: {stats['new']}\nВ работе: {stats['open']}\nЗакрыто: {stats['closed']}\n"
        "Команды: /stats, /queue"
    )

@router.message(Command("queue"))
async def queue(message: Message):
    if not await is_admin(message.from_user.id):
        return
    rows = await get_admin_queue()
    if not rows:
        await message.answer("Новых обращений нет.")
        return
    for t in rows:
        sent = await message.answer(
            f"<b>Обращение №{t['id']}</b>\\nПользователь: <code>{t['user_id']}</code>\\n"
            f"{escape(t['preview'] or 'Вложение или сообщение')}",
            reply_markup=new_ticket_card(t["id"])
        )
        await save_admin_card(t["id"], message.from_user.id, message.chat.id, sent.message_id)


@router.message(Command("stats"))
async def stats(message: Message):
    if not await is_admin(message.from_user.id):
        return
    s = await get_stats()
    await message.answer(
        "<b>Статистика</b>\n"
        f"Новые: {s['new']}\nВ работе: {s['open']}\nЗакрыто: {s['closed']}\n"
        f"Средняя оценка: {s['avg_rating'] or 'пока нет оценок'}"
    )

@router.message(Command("addadmin"))
async def addadmin(message: Message):
    if message.from_user.id not in OWNER_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /addadmin TELEGRAM_ID")
        return
    await add_admin(int(parts[1]))
    await message.answer("Администратор добавлен.")

@router.message(Command("deladmin"))
async def deladmin(message: Message):
    if message.from_user.id not in OWNER_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /deladmin TELEGRAM_ID")
        return
    await remove_admin(int(parts[1]))
    await message.answer("Администратор удалён из списка.")

@router.message(Command("ban"))
async def ban(message: Message):
    if message.from_user.id not in OWNER_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /ban TELEGRAM_ID")
        return
    await set_banned(int(parts[1]), True)
    await message.answer("Пользователь добавлен в чёрный список.")

@router.message(Command("unban"))
async def unban(message: Message):
    if message.from_user.id not in OWNER_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /unban TELEGRAM_ID")
        return
    await set_banned(int(parts[1]), False)
    await message.answer("Пользователь удалён из чёрного списка.")
