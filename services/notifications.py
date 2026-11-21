from config import OWNER_IDS, ADMIN_IDS
from database.queries import get_admin_ticket_cards, delete_admin_cards

async def remove_ticket_cards(bot, ticket_id, except_admin=None):
    cards = await get_admin_ticket_cards(ticket_id)
    for card in cards:
        if card["admin_id"] == except_admin:
            continue
        try:
            await bot.delete_message(card["chat_id"], card["message_id"])
        except Exception:
            # Telegram may reject deletion (e.g. old message); the DB claim is authoritative.
            pass
    await delete_admin_cards(ticket_id)
