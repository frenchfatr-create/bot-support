from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать в поддержку", callback_data="new_ticket")],
        [InlineKeyboardButton(text="📂 Мои обращения", callback_data="my_tickets"),
         InlineKeyboardButton(text="❓ Частые вопросы", callback_data="faq")]
    ])

def ticket_rating(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=str(i), callback_data=f"rate:{ticket_id}:{i}") for i in range(1, 6)
    ]])
