
from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config import OWNER_IDS, ADMIN_IDS

from database.queries import (
    get_ticket,
    claim_ticket,
    close_ticket,
    save_message,
    get_database_admin_ids,
    is_banned,
    get_active_user_ticket,
)

from keyboards.admin import ticket_actions
from keyboards.user import ticket_rating

from services.notifications import remove_ticket_cards
from services.tickets import (
    copy_user_message_to_admins,
    send_admin_reply,
)

router = Router()


# Проверка администратора
async def is_admin(user_id: int) -> bool:
    database_admins = await get_database_admin_ids()

    return (
        user_id in OWNER_IDS
        or user_id in ADMIN_IDS
        or user_id in database_admins
    )


# Состояние ответа администратора
class AdminFlow(StatesGroup):
    waiting_reply = State()


# Безопасное получение ID обращения
def parse_ticket_id(data: str):
    try:
        parts = data.split(":")

        if len(parts) != 2:
            return None

        ticket_id = int(parts[1])

        if ticket_id <= 0:
            return None

        return ticket_id

    except (ValueError, AttributeError, TypeError):
        return None


# Безопасное редактирование карточки
async def safe_edit_message(
    call: CallbackQuery,
    text: str,
    reply_markup=None,
):
    if not call.message:
        return

    try:
        await call.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except Exception:
        try:
            await call.message.answer(
                text,
                reply_markup=reply_markup,
            )
        except Exception:
            pass


# Фильтр: сообщение пользователя относится к активному обращению
class ActiveTicketMessageFilter(BaseFilter):

    async def __call__(
        self,
        message: Message,
        state: FSMContext,
    ):
        if not message.from_user:
            return False

        user_id = message.from_user.id

        # Администраторы не должны попадать сюда
        if await is_admin(user_id):
            return False

        # Не перехватываем сообщения во время FSM-состояния
        if await state.get_state() is not None:
            return False

        # Заблокированные пользователи
        if await is_banned(user_id):
            return False

        ticket = await get_active_user_ticket(user_id)

        if not ticket:
            return False

        return {"active_ticket": ticket}


# =====================================================
# ПРИНЯТИЕ ОБРАЩЕНИЯ
# callback_data: claim:ID
# =====================================================

@router.callback_query(F.data.startswith("claim:"))
async def claim(call: CallbackQuery):

    if not await is_admin(call.from_user.id):
        await call.answer(
            "Нет доступа.",
            show_alert=True,
        )
        return

    ticket_id = parse_ticket_id(call.data)

    if ticket_id is None:
        await call.answer(
            "Некорректный номер обращения.",
            show_alert=True,
        )
        return

    ticket = await get_ticket(ticket_id)

    if not ticket:
        await call.answer(
            "Обращение не найдено.",
            show_alert=True,
        )
        return

    if ticket["status"] != "open":
        await call.answer(
            "Обращение уже закрыто.",
            show_alert=True,
        )
        return

    if ticket["admin_id"] is not None:
        await call.answer(
            "Обращение уже принято.",
            show_alert=True,
        )
        return

    ok = await claim_ticket(
        ticket_id,
        call.from_user.id,
    )

    if not ok:
        await call.answer(
            "Не удалось принять обращение. Возможно, его уже забрали.",
            show_alert=True,
        )
        return

    try:
        await remove_ticket_cards(
            call.bot,
            ticket_id,
            except_admin=call.from_user.id,
        )
    except Exception:
        pass

    await safe_edit_message(
        call,
        f"Вы приняли обращение №{ticket_id}.\n"
        "Теперь можете отвечать пользователю.",
        reply_markup=ticket_actions(ticket_id),
    )

    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"Ваше обращение №{ticket_id} принято специалистом. "
            "Пожалуйста, ожидайте ответа.",
        )
    except Exception:
        pass

    await call.answer("Обращение закреплено за вами.")


# =====================================================
# НАЧАТЬ ОТВЕТ
# callback_data: reply:ID
# =====================================================

@router.callback_query(F.data.startswith("reply:"))
async def begin_reply(
    call: CallbackQuery,
    state: FSMContext,
):

    if not await is_admin(call.from_user.id):
        await call.answer(
            "Нет доступа.",
            show_alert=True,
        )
        return

    ticket_id = parse_ticket_id(call.data)

    if ticket_id is None:
        await call.answer(
            "Некорректный номер обращения.",
            show_alert=True,
        )
        return

    ticket = await get_ticket(ticket_id)

    if not ticket or ticket["status"] != "open":
        await call.answer(
            "Обращение не найдено или закрыто.",
            show_alert=True,
        )
        return

    if (
        ticket["admin_id"] != call.from_user.id
        and call.from_user.id not in OWNER_IDS
    ):
        await call.answer(
            "Это обращение не закреплено за вами.",
            show_alert=True,
        )
        return

    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AdminFlow.waiting_reply)

    await call.answer()

    if call.message:
        await call.message.answer(
            f"Введите ответ для обращения №{ticket_id}."
        )


# =====================================================
# ОТПРАВКА ОТВЕТА ПОЛЬЗОВАТЕЛЮ
# =====================================================

@router.message(AdminFlow.waiting_reply)
async def admin_reply(
    message: Message,
    state: FSMContext,
):

    if not await is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    if not ticket_id:
        await state.clear()
        await message.answer("Не удалось определить обращение.")
        return

    ticket = await get_ticket(ticket_id)

    if not ticket or ticket["status"] != "open":
        await state.clear()
        await message.answer(
            "Обращение уже закрыто или не найдено."
        )
        return

    if (
        ticket["admin_id"] != message.from_user.id
        and message.from_user.id not in OWNER_IDS
    ):
        await state.clear()
        await message.answer(
            "У вас нет прав отвечать в этом обращении."
        )
        return

    if not (
        message.text
        or message.caption
        or message.photo
        or message.document
    ):
        await message.answer(
            "Отправьте текст, фото или документ."
        )
        return

    try:
        await send_admin_reply(
            message,
            ticket_id,
            ticket["user_id"],
        )

        await message.answer(
            f"Ответ отправлен пользователю "
            f"по обращению №{ticket_id}."
        )

        await state.clear()

    except Exception:
        await message.answer(
            "Не удалось отправить ответ. Попробуйте ещё раз."
        )


# =====================================================
# ЗАКРЫТИЕ ОБРАЩЕНИЯ
# callback_data: close:ID
# =====================================================

@router.callback_query(F.data.startswith("close:"))
async def close(call: CallbackQuery):

    if not await is_admin(call.from_user.id):
        await call.answer(
            "Нет доступа.",
            show_alert=True,
        )
        return

    ticket_id = parse_ticket_id(call.data)

    if ticket_id is None:
        await call.answer(
            "Некорректный номер обращения.",
            show_alert=True,
        )
        return

    ticket = await get_ticket(ticket_id)

    if not ticket:
        await call.answer(
            "Обращение не найдено.",
            show_alert=True,
        )
        return

    if (
        ticket["admin_id"] != call.from_user.id
        and call.from_user.id not in OWNER_IDS
    ):
        await call.answer(
            "Нет доступа к этому обращению.",
            show_alert=True,
        )
        return

    if ticket["status"] != "open":
        await call.answer(
            "Обращение уже закрыто.",
            show_alert=True,
        )
        return

    ok = await close_ticket(ticket_id)

    if not ok:
        await call.answer(
            "Не удалось закрыть обращение.",
            show_alert=True,
        )
        return

    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"Обращение №{ticket_id} закрыто. "
            "Оцените, пожалуйста, качество поддержки:",
            reply_markup=ticket_rating(ticket_id),
        )
    except Exception:
        pass

    await safe_edit_message(
        call,
        f"Обращение №{ticket_id} закрыто.",
    )

    await call.answer("Обращение закрыто.")


# =====================================================
# ПЕРЕСЫЛКА СООБЩЕНИЙ ПОЛЬЗОВАТЕЛЯ
# =====================================================

@router.message(
    F.chat.type == "private",
    ActiveTicketMessageFilter(),
)
async def forward_followup(
    message: Message,
    active_ticket: dict,
):

    ticket = active_ticket

    ticket_id = ticket["id"]

    await save_message(
        ticket_id,
        "user",
        message.from_user.id,
        message,
    )

    if ticket["admin_id"]:
        await copy_user_message_to_admins(
            message,
            ticket["admin_id"],
            ticket_id,
        )
