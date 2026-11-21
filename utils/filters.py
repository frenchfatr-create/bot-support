from config import OWNER_IDS, ADMIN_IDS

def is_admin(user_id: int) -> bool:
    return user_id in OWNER_IDS or user_id in ADMIN_IDS
