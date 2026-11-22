
from aiogram import Router, F
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
)
from keyboards.admin import ticket_actions
from keyboards.user import ticket_rating
from services.notifications import remove_ticket_cards
from services.tickets import copy_user_message_to_admins, send_admin_reply

router = Router()


async def is_admin(user_id: int) -> bool:
    return (
        user_id in OWNER_IDS
        or user_id in ADMIN_IDS
        or user_id in await get_database_admin_ids()
    )


class AdminFlow(StatesGroup):
    waiting_reply = State()


def parse_ticket_id(data: str):
    """Безопасно получает ID обращения из callback_data."""
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


async def safe_edit_message(call: CallbackQuery, text: str, reply_markup=None):
    """Редактирует карточку, не ломая обработчик при ошибке Telegram."""
    try:
        await call.message.edit_text(
            text,
            reply_markup=reply_markup
        )
    except Exception:
        try:
            await call.message.answer(
                text,
                reply_markup=reply_markup
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("claim:"))
async def claim(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = parse_ticket_id(call.data)

    if ticket_id is None:
        await call.answer("Некорректный номер обращения.", show_alert=True)
        return

    ticket = await get_ticket(ticket_id)

    if not ticket:
        await call.answer("Обращение не найдено.", show_alert=True)
        return

    ok = await claim_ticket(ticket_id, call.from_user.id)

    if not ok:
        await call.answer(
            "Обращение уже забрал другой администратор или оно закрыто.",
            show_alert=True
        )
        try:
            await call.message.delete()
        except Exception:
            pass
        return

    try:
        await remove_ticket_cards(
            call.bot,
            ticket_id,
            except_admin=call.from_user.id
        )
    except Exception:
        pass

    await safe_edit_message(
        call,
        f"Вы приняли обращение №{ticket_id}.\n"
        "Теперь можете отвечать пользователю.",
        reply_markup=ticket_actions(ticket_id)
    )

    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"Ваше обращение №{ticket_id} принято специалистом. "
            "Пожалуйста, ожидайте ответа."
        )
    except Exception:
        pass

    await call.answer("Обращение закреплено за вами.")


@router.callback_query(F.data.startswith("reply:"))
async def begin_reply(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = parse_ticket_id(call.data)

    if ticket_id is None:
        await call.answer("Некорректный номер обращения.", show_alert=True)
        return

    ticket = await get_ticket(ticket_id)

    if not ticket or ticket["status"] != "open":
        await call.answer("Обращение не найдено или закрыто.", show_alert=True)
        return

    if (
        ticket["admin_id"] != call.from_user.id
        and call.from_user.id not in OWNER_IDS
    ):
        await call.answer(
            "Это обращение не закреплено за вами.",
            show_alert=True
        )
        return

    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AdminFlow.waiting_reply)

    await call.answer()

    try:
        await call.message.answer(
            f"Введите ответ для обращения №{ticket_id}."
        )
    except Exception:
        pass


@router.message(AdminFlow.waiting_reply)
async def admin_reply(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    ticket = await get_ticket(ticket_id) if ticket_id else None

    if not ticket or ticket["status"] != "open":
        await state.clear()
        await message.answer("Обращение уже закрыто или не найдено.")
        return

    if (
        ticket["admin_id"] != message.from_user.id
        and message.from_user.id not in OWNER_IDS
    ):
        await message.answer(
            "У вас нет прав отвечать в этом обращении."
        )
        await state.clear()
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
            ticket["user_id"]
        )
        await message.answer(
            f"Ответ отправлен пользователю по обращению №{ticket_id}."
        )
        await state.clear()

    except Exception:
        await message.answer(
            "Не удалось отправить ответ. Попробуйте ещё раз."
        )


@router.callback_query(F.data.startswith("close:"))
async def close(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = parse_ticket_id(call.data)

    if ticket_id is None:
        await call.answer("Некорректный номер обращения.", show_alert=True)
        return

    ticket = await get_ticket(ticket_id)

    if not ticket:
        await call.answer("Обращение не найдено.", show_alert=True)
        return

    if (
        ticket["admin_id"] != call.from_user.id
        and call.from_user.id not in OWNER_IDS
    ):
        await call.answer(
            "Нет доступа к этому обращению.",
            show_alert=True
        )
        return

    if ticket["status"] != "open":
        await call.answer("Обращение уже закрыто.", show_alert=True)
        return

    if await close_ticket(ticket_id):
        try:
            await call.bot.send_message(
                ticket["user_id"],
                f"Обращение №{ticket_id} закрыто. "
                "Оцените, пожалуйста, качество поддержки:",
                reply_markup=ticket_rating(ticket_id)
            )
        except Exception:
            pass

        await safe_edit_message(
            call,
            f"Обращение №{ticket_id} закрыто."
        )

        await call.answer("Закрыто.")

    else:
        await call.answer(
            "Не удалось закрыть обращение.",
            show_alert=True
        )


@router.message(F.chat.type == "private")
async def forward_followup(message: Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        return

    if await state.get_state():
        return

    if await is_banned(message.from_user.id):
        return

    from database.queries import get_active_user_ticket

    ticket = await get_active_user_ticket(message.from_user.id)

    if not ticket:
        return

    await save_message(
        ticket["id"],
        "user",
        message.from_user.id,
        message
    )

    if ticket["admin_id"]:
        await copy_user_message_to_admins(
            message,
            ticket["admin_id"],
            ticket["id"]
        )


@router.callback_query()
async def unknown_callback(call: CallbackQuery):
    """Ответ на неизвестные или устаревшие inline-кнопки."""
    await call.answer(
        "Эта кнопка устарела или больше не поддерживается. "
        "Откройте меню заново.",
        show_alert=True
    )
