from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def new_ticket_card(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🤝 Взять обращение", callback_data=f"claim:{ticket_id}")
    ]])

def ticket_actions(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"reply:{ticket_id}")],
        [InlineKeyboardButton(text="✅ Закрыть обращение", callback_data=f"close:{ticket_id}")]
    ])
