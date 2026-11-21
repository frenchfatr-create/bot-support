from config import OWNER_IDS, ADMIN_IDS
from html import escape
from database.queries import create_ticket_row, save_message, save_admin_card, get_database_admin_ids
from keyboards.admin import new_ticket_card

async def create_ticket(message):
    ticket_id = await create_ticket_row(message.from_user.id)
    await save_message(ticket_id, "user", message.from_user.id, message)
    preview = escape((message.text or message.caption or "Фото или документ")[:700])
    for admin_id in OWNER_IDS | ADMIN_IDS | await get_database_admin_ids():
        try:
            sent = await message.bot.send_message(
                admin_id,
                f"<b>Новое обращение №{ticket_id}</b>\n"
                f"Пользователь: <code>{message.from_user.id}</code>\n"
                f"{preview}",
                reply_markup=new_ticket_card(ticket_id)
            )
            await save_admin_card(ticket_id, admin_id, admin_id, sent.message_id)
            if message.photo or message.document:
                await message.copy_to(admin_id)
        except Exception:
            # Admin must start the bot first; they can use /queue later.
            continue
    return ticket_id

async def copy_user_message_to_admins(message, admin_id, ticket_id):
    try:
        await message.copy_to(admin_id)
    except Exception:
        pass

async def send_admin_reply(message, ticket_id, user_id):
    await message.copy_to(user_id)
    await save_message(ticket_id, "admin", message.from_user.id, message)
