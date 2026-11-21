from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from database.queries import upsert_user, is_banned, list_user_tickets, get_ticket
from keyboards.user import main_menu, ticket_rating
from services.tickets import create_ticket
from config import OWNER_IDS, ADMIN_IDS

router = Router()

class UserFlow(StatesGroup):
    waiting_ticket = State()

@router.callback_query(F.data == "new_ticket")
async def new_ticket(call: CallbackQuery, state: FSMContext):
    if await is_banned(call.from_user.id):
        await call.answer("Доступ ограничен.", show_alert=True)
        return
    await state.set_state(UserFlow.waiting_ticket)
    await call.message.answer("Опишите проблему одним сообщением. Можно прикрепить фото или документ.")
    await call.answer()

@router.message(UserFlow.waiting_ticket)
async def submit_ticket(message: Message, state: FSMContext):
    if await is_banned(message.from_user.id):
        await state.clear()
        await message.answer("Доступ к поддержке ограничен.")
        return
    if not (message.text or message.caption or message.photo or message.document):
        await message.answer("Пожалуйста, отправьте текст, фотографию или документ.")
        return
    ticket_id = await create_ticket(message)
    await state.clear()
    await message.answer(
        f"Обращение №{ticket_id} создано. Специалисты получили уведомление. Пожалуйста, ожидайте ответа.",
        reply_markup=main_menu()
    )

@router.callback_query(F.data == "my_tickets")
async def my_tickets(call: CallbackQuery):
    rows = await list_user_tickets(call.from_user.id)
    if not rows:
        await call.message.answer("У вас пока нет обращений.")
    else:
        lines = ["<b>Ваши обращения:</b>"]
        for t in rows:
            lines.append(f"№{t['id']} — {t['status_label']}")
        await call.message.answer("\n".join(lines))
    await call.answer()

@router.message(Command("mytickets"))
async def my_tickets_command(message: Message):
    rows = await list_user_tickets(message.from_user.id)
    if not rows:
        await message.answer("У вас пока нет обращений.")
        return
    await message.answer("\n".join(f"№{t['id']} — {t['status_label']}" for t in rows))

@router.callback_query(F.data == "faq")
async def faq_callback(call: CallbackQuery):
    await call.message.answer(
        "<b>Частые вопросы</b>\n"
        "1. Как обратиться в поддержку? Нажмите «Написать в поддержку».\n"
        "2. Как узнать статус? Откройте «Мои обращения».\n"
        "3. Можно ли отправить файл? Да, поддерживаются фотографии и документы."
    )
    await call.answer()

@router.message(Command("faq"))
async def faq(message: Message):
    await message.answer(
        "<b>Частые вопросы</b>\n"
        "1. Как обратиться в поддержку? Нажмите «Написать в поддержку».\n"
        "2. Как узнать статус? Откройте «Мои обращения».\n"
        "3. Можно ли отправить файл? Да, поддерживаются фотографии и документы."
    )

@router.callback_query(F.data.startswith("rate:"))
async def rate_ticket(call: CallbackQuery):
    try:
        _, ticket_id, score = call.data.split(":")
        ticket_id, score = int(ticket_id), int(score)
    except ValueError:
        await call.answer("Некорректная оценка.", show_alert=True)
        return
    ticket = await get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != call.from_user.id or ticket["status"] != "closed":
        await call.answer("Оценить это обращение нельзя.", show_alert=True)
        return
    from database.queries import save_rating
    await save_rating(ticket_id, call.from_user.id, score)
    await call.message.edit_text("Спасибо за вашу оценку!")
    await call.answer()
