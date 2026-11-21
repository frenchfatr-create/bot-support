from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from database.queries import upsert_user, is_banned
from keyboards.user import main_menu

router = Router()

@router.message(CommandStart())
async def start(message: Message):
    await upsert_user(message.from_user)
    if await is_banned(message.from_user.id):
        await message.answer("Доступ к поддержке ограничен.")
        return
    await message.answer(
        "Здравствуйте! Это служба поддержки.\n\n"
        "Выберите действие в меню ниже.",
        reply_markup=main_menu()
    )
