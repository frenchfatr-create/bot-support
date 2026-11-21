from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_IDS, ADMIN_IDS
from database.queries import (
    get_stats, add_admin, remove_admin, set_banned,
    get_database_admin_ids, get_admin_queue, save_admin_card,
    get_banned_users,
)
from keyboards.admin import new_ticket_card

router = Router()


async def is_admin(user_id: int) -> bool:
    return (
        user_id in OWNER_IDS
        or user_id in ADMIN_IDS
        or user_id in await get_database_admin_ids()
    )


def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


@router.message(Command("adminhelp"))
async def admin_help(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "<b>Команды администрации</b>\n\n"
        "<b>Для всех администраторов:</b>\n"
        "/admin — панель поддержки\n"
        "/queue — новые обращения\n"
        "/stats — статистика\n"
        "/adminhelp — список команд\n\n"
        "<b>Только для главного администратора:</b>\n"
        "/addadmin ID — добавить администратора\n"
        "/deladmin ID — удалить администратора\n"
        "/ban ID — заблокировать пользователя\n"
        "/unban ID — снять блокировку\n"
        "/bans — список заблокированных пользователей"
    )


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    stats = await get_stats()
    await message.answer(
        "<b>Панель поддержки</b>\n"
        f"Новые: {stats['new']}\nВ работе: {stats['open']}\nЗакрыто: {stats['closed']}\n"
        "Команды: /adminhelp, /queue, /stats"
    )


@router.message(Command("queue"))
async def queue(message: Message):
    if not await is_admin(message.from_user.id):
        return
    rows = await get_admin_queue()
    if not rows:
        await message.answer("Новых обращений нет.")
        return
    for ticket in rows:
        sent = await message.answer(
            f"<b>Обращение №{ticket['id']}</b>\n"
            f"Пользователь: <code>{ticket['user_id']}</code>\n"
            f"{escape(ticket['preview'] or 'Вложение или сообщение')}",
            reply_markup=new_ticket_card(ticket["id"]),
        )
        await save_admin_card(
            ticket["id"], message.from_user.id, message.chat.id, sent.message_id
        )


@router.message(Command("stats"))
async def stats(message: Message):
    if not await is_admin(message.from_user.id):
        return
    data = await get_stats()
    await message.answer(
        "<b>Статистика</b>\n"
        f"Новые: {data['new']}\n"
        f"В работе: {data['open']}\n"
        f"Закрыто: {data['closed']}\n"
        f"Средняя оценка: {data['avg_rating'] or 'пока нет оценок'}"
    )


@router.message(Command("addadmin"))
async def addadmin(message: Message):
    if not is_owner(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /addadmin TELEGRAM_ID")
        return
    user_id = int(parts[1])
    if user_id in OWNER_IDS:
        await message.answer("Этот пользователь уже является главным администратором.")
        return
    await add_admin(user_id)
    await message.answer(f"Администратор {user_id} добавлен.")


@router.message(Command("deladmin"))
async def deladmin(message: Message):
    if not is_owner(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /deladmin TELEGRAM_ID")
        return
    user_id = int(parts[1])
    await remove_admin(user_id)
    await message.answer(f"Администратор {user_id} удалён из списка.")


@router.message(Command("ban"))
async def ban(message: Message):
    if not is_owner(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /ban TELEGRAM_ID")
        return
    user_id = int(parts[1])
    db_admins = await get_database_admin_ids()
    if user_id in OWNER_IDS or user_id in ADMIN_IDS or user_id in db_admins:
        await message.answer("Нельзя заблокировать администратора.")
        return
    await set_banned(user_id, True)
    await message.answer(f"Пользователь {user_id} добавлен в чёрный список.")


@router.message(Command("unban"))
async def unban(message: Message):
    if not is_owner(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /unban TELEGRAM_ID")
        return
    user_id = int(parts[1])
    await set_banned(user_id, False)
    await message.answer(f"Пользователь {user_id} удалён из чёрного списка.")


@router.message(Command("bans"))
async def bans(message: Message):
    if not is_owner(message.from_user.id):
        return
    users = await get_banned_users()
    if not users:
        await message.answer("Чёрный список пуст.")
        return
    lines = ["<b>Чёрный список</b>"]
    for item in users[:100]:
        lines.append(
            f"• <code>{item['user_id']}</code> — {escape(str(item['created_at']))}"
        )
    if len(users) > 100:
        lines.append(f"\nПоказаны первые 100 из {len(users)}.")
    await message.answer("\n".join(lines))
