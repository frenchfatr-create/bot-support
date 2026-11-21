from .start import router as start_router
from .user import router as user_router
from .admin import router as admin_router
from .tickets import router as tickets_router


def setup_routers(dp):
    dp.include_router(start_router)
    dp.include_router(user_router)
    # Check admin commands before the ticket-reply FSM handler.
    dp.include_router(admin_router)
    dp.include_router(tickets_router)
