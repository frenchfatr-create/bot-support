from database.db import connect

async def upsert_user(user):
    async with connect() as db:
        await db.execute(
            "INSERT INTO users(user_id, username, full_name) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
            (user.id, user.username, user.full_name))
        await db.commit()

async def is_banned(user_id):
    async with connect() as db:
        cur = await db.execute("SELECT 1 FROM blacklist WHERE user_id=?", (user_id,))
        return await cur.fetchone() is not None

async def create_ticket_row(user_id):
    async with connect() as db:
        cur = await db.execute("INSERT INTO tickets(user_id) VALUES(?)", (user_id,))
        await db.commit()
        return cur.lastrowid

async def save_message(ticket_id, role, sender_id, message):
    text = message.text or message.caption or ""
    content_type, file_id = "text", None
    if message.photo:
        content_type, file_id = "photo", message.photo[-1].file_id
    elif message.document:
        content_type, file_id = "document", message.document.file_id
    async with connect() as db:
        await db.execute(
            "INSERT INTO messages(ticket_id,sender_role,sender_id,content_type,text,file_id) VALUES(?,?,?,?,?,?)",
            (ticket_id, role, sender_id, content_type, text, file_id))
        await db.commit()

async def get_ticket(ticket_id):
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def claim_ticket(ticket_id, admin_id):
    async with connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "UPDATE tickets SET status='open', admin_id=? WHERE id=? AND status='new' AND admin_id IS NULL",
            (admin_id, ticket_id))
        await db.commit()
        return cur.rowcount == 1

async def close_ticket(ticket_id):
    async with connect() as db:
        cur = await db.execute(
            "UPDATE tickets SET status='closed', closed_at=CURRENT_TIMESTAMP WHERE id=? AND status='open'",
            (ticket_id,))
        await db.commit()
        return cur.rowcount == 1

async def list_user_tickets(user_id):
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute("SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,))
        rows = await cur.fetchall()
        labels = {"new": "Ожидает специалиста", "open": "В работе", "closed": "Закрыто"}
        return [dict(r, status_label=labels.get(r["status"], r["status"])) for r in rows]

async def get_active_user_ticket(user_id):
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute(
            "SELECT * FROM tickets WHERE user_id=? AND status IN ('new','open') ORDER BY id DESC LIMIT 1",
            (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def get_admin_queue():
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute("""
            SELECT t.*, (SELECT text FROM messages m WHERE m.ticket_id=t.id ORDER BY m.id LIMIT 1) AS preview
            FROM tickets t WHERE t.status='new' ORDER BY t.id
        """)
        return [dict(r) for r in await cur.fetchall()]

async def save_admin_card(ticket_id, admin_id, chat_id, message_id):
    async with connect() as db:
        await db.execute("INSERT OR REPLACE INTO admin_cards VALUES(?,?,?,?)",
                         (ticket_id, admin_id, chat_id, message_id))
        await db.commit()

async def get_admin_ticket_cards(ticket_id):
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute("SELECT * FROM admin_cards WHERE ticket_id=?", (ticket_id,))
        return [dict(r) for r in await cur.fetchall()]

async def delete_admin_cards(ticket_id):
    async with connect() as db:
        await db.execute("DELETE FROM admin_cards WHERE ticket_id=?", (ticket_id,))
        await db.commit()

async def get_stats():
    async with connect() as db:
        cur = await db.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status")
        counts = dict(await cur.fetchall())
        cur = await db.execute("SELECT AVG(score) FROM ratings")
        avg = (await cur.fetchone())[0]
        return {"new": counts.get("new", 0), "open": counts.get("open", 0),
                "closed": counts.get("closed", 0), "avg_rating": round(avg, 2) if avg else None}

async def add_admin(user_id):
    async with connect() as db:
        await db.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (user_id,))
        await db.commit()

async def remove_admin(user_id):
    async with connect() as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        await db.commit()

async def set_banned(user_id, banned):
    async with connect() as db:
        if banned:
            await db.execute("INSERT OR IGNORE INTO blacklist(user_id) VALUES(?)", (user_id,))
        else:
            await db.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
        await db.commit()

async def save_rating(ticket_id, user_id, score):
    async with connect() as db:
        await db.execute("INSERT OR REPLACE INTO ratings(ticket_id,user_id,score) VALUES(?,?,?)",
                         (ticket_id, user_id, score))
        await db.commit()


async def get_database_admin_ids():
    async with connect() as db:
        cur = await db.execute("SELECT user_id FROM admins")
        return {row[0] for row in await cur.fetchall()}
