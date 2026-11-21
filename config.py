import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_IDS = {
    int(x) for x in os.getenv("OWNER_IDS", "").replace(" ", "").split(",") if x
}
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}
DB_PATH = os.getenv("DB_PATH", "data/support.sqlite3")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")
if not OWNER_IDS:
    raise RuntimeError("OWNER_IDS is empty.")