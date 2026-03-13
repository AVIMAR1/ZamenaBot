# -*- coding: utf-8 -*-
"""SQLite база данных: пользователи, замены, тикеты, каталог (город → компания → объект → позиции)."""

import json
import os
import sqlite3
import threading
from typing import Any, List, Optional

import config

_db_path = os.path.join(config.DATA_DIR, "zamena.db")
_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(_db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init_db()
    return _conn


def _init_db():
    conn = _conn
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            city TEXT, company TEXT, object TEXT,
            username TEXT, name TEXT,
            full_name TEXT,
            supervisor_id INTEGER,
            replaced_count INTEGER DEFAULT 0,
            was_replaced_count INTEGER DEFAULT 0,
            notify_digest INTEGER DEFAULT 1,
            notify_new_enabled INTEGER DEFAULT 0,
            notify_positions TEXT,
            notify_shift_keys TEXT,
            banned_until TEXT,
            support_ban_until TEXT,
            support_ban_reason TEXT,
            trust_score REAL DEFAULT 50,
            daily_refuse_count INTEGER DEFAULT 0,
            daily_refuse_date TEXT,
            last_digest_msg_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS replacements (
            id TEXT PRIMARY KEY,
            author_id INTEGER, author_username TEXT,
            for_friend_id INTEGER, for_friend_username TEXT, for_friend_full_name TEXT,
            city TEXT, company TEXT, object TEXT, position TEXT,
            shift TEXT, shift_key TEXT, date_from TEXT, date_to TEXT, date_text TEXT,
            active INTEGER DEFAULT 1, confirmed INTEGER DEFAULT 0,
            taken_by_id INTEGER, taken_by_username TEXT,
            requested_by_id INTEGER, requested_by_username TEXT,
            start_notified INTEGER DEFAULT 0,
            pay_enabled INTEGER DEFAULT 0,
            pay_amount_byn REAL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            user_id INTEGER, username TEXT,
            messages TEXT, closed INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS catalog_cities (name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS catalog_companies (city TEXT, name TEXT, PRIMARY KEY(city, name));
        CREATE TABLE IF NOT EXISTS catalog_objects (city TEXT, company TEXT, name TEXT, PRIMARY KEY(city, company, name));
        CREATE TABLE IF NOT EXISTS catalog_positions (city TEXT, company TEXT, object_name TEXT, name TEXT, PRIMARY KEY(city, company, object_name, name));
        CREATE TABLE IF NOT EXISTS object_shifts (
            city TEXT,
            company TEXT,
            object_name TEXT,
            shift_key TEXT,          -- 'day' / 'night'
            start_time TEXT,         -- 'HH:MM'
            end_time TEXT,           -- 'HH:MM'
            PRIMARY KEY (city, company, object_name, shift_key)
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            rating INTEGER,
            text TEXT,
            admin_reply TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS review_reactions (
            review_id INTEGER,
            user_id INTEGER,
            value INTEGER,           -- 1 = like, -1 = dislike
            PRIMARY KEY (review_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS supervisors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            username TEXT,
            telegram_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS object_access (
            city TEXT,
            company TEXT,
            object_name TEXT,
            require_mode TEXT DEFAULT 'ANY',  -- ANY | ALL
            PRIMARY KEY (city, company, object_name)
        );

        CREATE TABLE IF NOT EXISTS object_access_chats (
            city TEXT,
            company TEXT,
            object_name TEXT,
            chat_id TEXT,            -- '@channel' or numeric id as string
            PRIMARY KEY (city, company, object_name, chat_id)
        );

        CREATE TABLE IF NOT EXISTS friends (
            owner_id INTEGER,
            friend_id INTEGER,
            PRIMARY KEY (owner_id, friend_id)
        );
    """)
    conn.commit()
    _migrate_schema(conn)
    _maybe_migrate_json()


def _migrate_schema(conn: sqlite3.Connection):
    """Добавление недостающих колонок/таблиц при обновлении версии."""
    # Users
    cur = conn.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in cur.fetchall()}
    if "full_name" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
    if "supervisor_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN supervisor_id INTEGER")
    if "notify_digest" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN notify_digest INTEGER DEFAULT 1")
    if "notify_new_enabled" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN notify_new_enabled INTEGER DEFAULT 0")
    if "notify_positions" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN notify_positions TEXT")
    if "notify_shift_keys" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN notify_shift_keys TEXT")
    if "banned_until" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN banned_until TEXT")
    if "support_ban_until" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN support_ban_until TEXT")
    if "support_ban_reason" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN support_ban_reason TEXT")
    if "trust_score" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN trust_score REAL DEFAULT 50")
    if "daily_refuse_count" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN daily_refuse_count INTEGER DEFAULT 0")
    if "daily_refuse_date" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN daily_refuse_date TEXT")
    if "last_digest_msg_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN last_digest_msg_id INTEGER")

    # Replacements
    cur = conn.execute("PRAGMA table_info(replacements)")
    rcols = {row[1] for row in cur.fetchall()}
    if "start_notified" not in rcols:
        conn.execute("ALTER TABLE replacements ADD COLUMN start_notified INTEGER DEFAULT 0")
    if "for_friend_id" not in rcols:
        conn.execute("ALTER TABLE replacements ADD COLUMN for_friend_id INTEGER")
    if "for_friend_username" not in rcols:
        conn.execute("ALTER TABLE replacements ADD COLUMN for_friend_username TEXT")
    if "for_friend_full_name" not in rcols:
        conn.execute("ALTER TABLE replacements ADD COLUMN for_friend_full_name TEXT")
    if "pay_enabled" not in rcols:
        conn.execute("ALTER TABLE replacements ADD COLUMN pay_enabled INTEGER DEFAULT 0")
    if "pay_amount_byn" not in rcols:
        conn.execute("ALTER TABLE replacements ADD COLUMN pay_amount_byn REAL")

    # Object shifts table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS object_shifts (
            city TEXT,
            company TEXT,
            object_name TEXT,
            shift_key TEXT,
            start_time TEXT,
            end_time TEXT,
            PRIMARY KEY (city, company, object_name, shift_key)
        )
    """)

    # Reviews tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            rating INTEGER,
            text TEXT,
            admin_reply TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS review_reactions (
            review_id INTEGER,
            user_id INTEGER,
            value INTEGER,
            PRIMARY KEY (review_id, user_id)
        )
    """)

    # Supervisors
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supervisors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            username TEXT,
            telegram_id INTEGER
        )
    """)

    # Object access requirements
    conn.execute("""
        CREATE TABLE IF NOT EXISTS object_access (
            city TEXT,
            company TEXT,
            object_name TEXT,
            require_mode TEXT DEFAULT 'ANY',
            PRIMARY KEY (city, company, object_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS object_access_chats (
            city TEXT,
            company TEXT,
            object_name TEXT,
            chat_id TEXT,
            PRIMARY KEY (city, company, object_name, chat_id)
        )
    """)

    # Friends
    conn.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            owner_id INTEGER,
            friend_id INTEGER,
            PRIMARY KEY (owner_id, friend_id)
        )
    """)

    # Offers: "готов выйти на замену"
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id TEXT PRIMARY KEY,
            author_id INTEGER,
            author_username TEXT,
            city TEXT,
            company TEXT,
            object TEXT,
            positions_json TEXT,
            shift_key TEXT,
            date_from TEXT,
            date_to TEXT,
            date_text TEXT,
            pay_enabled INTEGER DEFAULT 0,
            pay_amount_byn REAL,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    conn.commit()


def _seed_catalog(conn):
    """Заполнить каталог только из config.DEFAULT_CATALOG."""
    conn.execute("DELETE FROM catalog_positions")
    conn.execute("DELETE FROM catalog_objects")
    conn.execute("DELETE FROM catalog_companies")
    conn.execute("DELETE FROM catalog_cities")
    cat = config.DEFAULT_CATALOG
    for city, companies in cat.items():
        if not isinstance(companies, dict):
            continue
        conn.execute("INSERT INTO catalog_cities VALUES (?)", (city,))
        for company, objects in companies.items():
            if not isinstance(objects, dict):
                continue
            conn.execute("INSERT INTO catalog_companies VALUES (?,?)", (city, company))
            for obj, positions in objects.items():
                conn.execute("INSERT INTO catalog_objects VALUES (?,?,?)", (city, company, obj))
                for p in (positions if isinstance(positions, list) else []):
                    conn.execute("INSERT INTO catalog_positions VALUES (?,?,?,?)", (city, company, obj, p))
    conn.commit()


def _maybe_migrate_json():
    """Каталог: если пусто — заполняем. Если старые данные (нет Гродно) — удаляем БД и создаём заново."""
    global _conn
    conn = _conn
    cur = conn.execute("SELECT name FROM catalog_cities")
    cities = [row[0] for row in cur.fetchall()]
    if not cities:
        # Пустая БД — заполняем из config
        _seed_catalog(conn)
        return
    if "Гродно" not in cities:
        # Старые данные (Москва, Казань и т.д.) — удаляем БД полностью
        conn.close()
        _conn = None
        try:
            if os.path.exists(_db_path):
                os.remove(_db_path)
        except Exception:
            pass
        os.makedirs(config.DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(_db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init_db()
        return
    conn.commit()


def _row_to_dict(row) -> dict:
    return dict(row) if row else {}


# --- Users ---
def get_user(telegram_id: int) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute(
            "SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["telegram_id"] = d["telegram_id"]
        return d


def save_user(telegram_id: int, user: dict):
    with _lock:
        _get_conn().execute(
            """INSERT OR REPLACE INTO users
               (telegram_id, city, company, object, username, name,
                full_name, supervisor_id,
                replaced_count, was_replaced_count,
                notify_digest, notify_new_enabled, notify_positions, notify_shift_keys,
                banned_until,
                support_ban_until, support_ban_reason,
                trust_score, daily_refuse_count, daily_refuse_date, last_digest_msg_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                telegram_id,
                user.get("city"),
                user.get("company"),
                user.get("object"),
                user.get("username", ""),
                user.get("name", ""),
                user.get("full_name"),
                user.get("supervisor_id"),
                user.get("replaced_count", 0),
                user.get("was_replaced_count", 0),
                1 if user.get("notify_digest", True) else 0,
                1 if user.get("notify_new_enabled", False) else 0,
                user.get("notify_positions"),
                user.get("notify_shift_keys"),
                user.get("banned_until"),
                user.get("support_ban_until"),
                user.get("support_ban_reason"),
                user.get("trust_score", 50),
                user.get("daily_refuse_count", 0),
                user.get("daily_refuse_date"),
                user.get("last_digest_msg_id"),
            )
        )
        _get_conn().commit()


def get_all_users() -> dict:
    with _lock:
        cur = _get_conn().execute("SELECT * FROM users")
        return {str(row["telegram_id"]): dict(row) for row in cur.fetchall()}


def get_banned_support_users() -> list:
    """Пользователи с активным баном поддержки (forever или until >= сегодня)."""
    from datetime import date
    today = date.today().isoformat()
    with _lock:
        cur = _get_conn().execute(
            """SELECT * FROM users
               WHERE support_ban_until IS NOT NULL AND support_ban_until != ''
               AND (support_ban_until = 'forever' OR support_ban_until >= ?)""",
            (today,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def reset_all_users():
    """Удалить всех пользователей из БД (для перерегистрации)."""
    with _lock:
        _get_conn().execute("DELETE FROM users")
        _get_conn().commit()


def get_users_page(city: str | None = None, company: str | None = None, obj: str | None = None,
                   page: int = 0, per_page: int = 10) -> tuple[list, int]:
    """Пагинация пользователей с фильтром по объекту. Возвращает (users, total)."""
    where = []
    params: list[Any] = []
    if city:
        where.append("city=?")
        params.append(city)
    if company:
        where.append("company=?")
        params.append(company)
    if obj:
        where.append("object=?")
        params.append(obj)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with _lock:
        cur = _get_conn().execute(f"SELECT COUNT(*) FROM users {where_sql}", tuple(params))
        total_row = cur.fetchone()
        total = int(total_row[0]) if total_row else 0
        offset = page * per_page
        cur = _get_conn().execute(
            f"SELECT * FROM users {where_sql} ORDER BY telegram_id LIMIT ? OFFSET ?",
            tuple(params + [per_page, offset]),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows], total


# --- Supervisors (администраторы) ---
def get_supervisors() -> list:
    with _lock:
        cur = _get_conn().execute("SELECT * FROM supervisors ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]


def add_supervisor(title: str, username: str | None = None, telegram_id: int | None = None) -> int:
    with _lock:
        cur = _get_conn().execute(
            "INSERT INTO supervisors (title, username, telegram_id) VALUES (?,?,?)",
            (title.strip(), (username or "").strip().lstrip("@"), telegram_id),
        )
        _get_conn().commit()
        return int(cur.lastrowid)


def delete_supervisor(sid: int):
    with _lock:
        _get_conn().execute("DELETE FROM supervisors WHERE id=?", (sid,))
        _get_conn().execute("UPDATE users SET supervisor_id=NULL WHERE supervisor_id=?", (sid,))
        _get_conn().commit()


def get_supervisor_by_id(sid: int) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute("SELECT * FROM supervisors WHERE id=?", (sid,))
        row = cur.fetchone()
    return dict(row) if row else None


def update_supervisor_username(sid: int, username: str):
    username = (username or "").strip().lstrip("@")
    with _lock:
        _get_conn().execute(
            "UPDATE supervisors SET username=? WHERE id=?",
            (username, sid),
        )
        _get_conn().commit()


def update_supervisor(sid: int, title: str, username: str | None, telegram_id: int | None):
    """Полное редактирование администратора: название, username, telegram_id."""
    title = (title or "").strip()
    username = (username or "").strip().lstrip("@") if username else None
    with _lock:
        _get_conn().execute(
            "UPDATE supervisors SET title=?, username=?, telegram_id=? WHERE id=?",
            (title, username, telegram_id, sid),
        )
        _get_conn().commit()


# --- Object access requirements (groups/channels membership) ---
def get_object_access(city: str, company: str, object_name: str) -> dict:
    with _lock:
        cur = _get_conn().execute(
            "SELECT require_mode FROM object_access WHERE city=? AND company=? AND object_name=?",
            (city, company, object_name),
        )
        row = cur.fetchone()
        mode = row[0] if row else "ANY"
        cur = _get_conn().execute(
            "SELECT chat_id FROM object_access_chats WHERE city=? AND company=? AND object_name=? ORDER BY chat_id",
            (city, company, object_name),
        )
        chats = [r[0] for r in cur.fetchall()]
    return {"require_mode": mode, "chats": chats}


def set_object_access_mode(city: str, company: str, object_name: str, require_mode: str):
    mode = "ALL" if require_mode == "ALL" else "ANY"
    with _lock:
        _get_conn().execute(
            "INSERT OR REPLACE INTO object_access (city, company, object_name, require_mode) VALUES (?,?,?,?)",
            (city, company, object_name, mode),
        )
        _get_conn().commit()


def add_object_access_chat(city: str, company: str, object_name: str, chat_id: str) -> bool:
    chat_id = chat_id.strip()
    if not chat_id:
        return False
    with _lock:
        _get_conn().execute(
            "INSERT OR IGNORE INTO object_access_chats (city, company, object_name, chat_id) VALUES (?,?,?,?)",
            (city, company, object_name, chat_id),
        )
        _get_conn().commit()
    return True


def remove_object_access_chat(city: str, company: str, object_name: str, chat_id: str):
    with _lock:
        _get_conn().execute(
            "DELETE FROM object_access_chats WHERE city=? AND company=? AND object_name=? AND chat_id=?",
            (city, company, object_name, chat_id),
        )
        _get_conn().commit()


# --- Friends ---
def add_friend(owner_id: int, friend_id: int) -> bool:
    if owner_id == friend_id:
        return False
    with _lock:
        _get_conn().execute(
            "INSERT OR IGNORE INTO friends (owner_id, friend_id) VALUES (?,?)",
            (owner_id, friend_id),
        )
        _get_conn().commit()
    return True


def remove_friend(owner_id: int, friend_id: int):
    with _lock:
        _get_conn().execute("DELETE FROM friends WHERE owner_id=? AND friend_id=?", (owner_id, friend_id))
        _get_conn().commit()


def get_friends(owner_id: int) -> list:
    with _lock:
        cur = _get_conn().execute(
            """SELECT u.* FROM friends f
               JOIN users u ON u.telegram_id = f.friend_id
               WHERE f.owner_id=?
               ORDER BY u.full_name, u.telegram_id""",
            (owner_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# --- Replacements ---
def get_replacements(active_only: bool = True, exclude_requested: bool = True) -> list:
    """exclude_requested=True: не показывать замены, на которые уже подали заявку."""
    with _lock:
        if active_only:
            cur = _get_conn().execute(
                """SELECT * FROM replacements WHERE active=1 AND confirmed=0
                   AND (requested_by_id IS NULL OR ?=1)""",
                (0 if exclude_requested else 1,))
        else:
            cur = _get_conn().execute("SELECT * FROM replacements")
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["active"] = bool(d.get("active", 1))
        d["confirmed"] = bool(d.get("confirmed", 0))
        result.append(d)
    return result


def get_replacement_by_id(rid: str) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute("SELECT * FROM replacements WHERE id=?", (rid,))
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["active"] = bool(d.get("active", 1))
    d["confirmed"] = bool(d.get("confirmed", 0))
    return d


def save_replacement(replacement: dict):
    with _lock:
        r = replacement
        _get_conn().execute(
            """INSERT OR REPLACE INTO replacements
               (id, author_id, author_username,
                for_friend_id, for_friend_username, for_friend_full_name,
                city, company, object, position,
                shift, shift_key, date_from, date_to, date_text,
                active, confirmed,
                taken_by_id, taken_by_username,
                requested_by_id, requested_by_username,
                start_notified,
                pay_enabled, pay_amount_byn)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r.get("id"), r.get("author_id"), r.get("author_username", ""),
             r.get("for_friend_id"), r.get("for_friend_username", ""), r.get("for_friend_full_name", ""),
             r.get("city"), r.get("company"), r.get("object"), r.get("position"),
             r.get("shift"), r.get("shift_key"), r.get("date_from"), r.get("date_to"), r.get("date_text"),
             1 if r.get("active", True) else 0, 1 if r.get("confirmed") else 0,
             r.get("taken_by_id"), r.get("taken_by_username", ""),
             r.get("requested_by_id"), r.get("requested_by_username", ""),
             1 if r.get("start_notified", 0) else 0,
             1 if r.get("pay_enabled", 0) else 0,
             r.get("pay_amount_byn"))
        )
        _get_conn().commit()


def update_replacement_usernames(rid: str, author_username: str | None = None,
                                requested_by_username: str | None = None,
                                taken_by_username: str | None = None):
    """Обновить username-поля у замены."""
    sets = []
    params: list[Any] = []
    if author_username is not None:
        sets.append("author_username=?")
        params.append(author_username)
    if requested_by_username is not None:
        sets.append("requested_by_username=?")
        params.append(requested_by_username)
    if taken_by_username is not None:
        sets.append("taken_by_username=?")
        params.append(taken_by_username)
    if not sets:
        return
    params.append(rid)
    with _lock:
        _get_conn().execute(
            f"UPDATE replacements SET {', '.join(sets)} WHERE id=?",
            tuple(params),
        )
        _get_conn().commit()


def repair_all_replacement_usernames():
    """Пройтись по replacements и синхронизировать username с таблицей users."""
    with _lock:
        cur = _get_conn().execute("SELECT id, author_id, requested_by_id, taken_by_id FROM replacements")
        rows = cur.fetchall()
    # вне лока: соберём user->username
    uids = set()
    for r in rows:
        for k in ("author_id", "requested_by_id", "taken_by_id"):
            if r[k]:
                uids.add(int(r[k]))
    user_map: dict[int, str] = {}
    if uids:
        with _lock:
            cur = _get_conn().execute(
                f"SELECT telegram_id, username FROM users WHERE telegram_id IN ({','.join(['?']*len(uids))})",
                tuple(uids),
            )
            for rr in cur.fetchall():
                user_map[int(rr[0])] = rr[1] or ""
    for r in rows:
        rid = r["id"]
        au = user_map.get(int(r["author_id"])) if r["author_id"] else None
        ru = user_map.get(int(r["requested_by_id"])) if r["requested_by_id"] else None
        tu = user_map.get(int(r["taken_by_id"])) if r["taken_by_id"] else None
        update_replacement_usernames(rid, author_username=au, requested_by_username=ru, taken_by_username=tu)


def get_my_replacements(telegram_id: int, active_only: bool = False) -> list:
    with _lock:
        if active_only:
            cur = _get_conn().execute(
                """SELECT * FROM replacements WHERE author_id=? AND active=1 AND confirmed=0""",
                (telegram_id,))
        else:
            cur = _get_conn().execute("SELECT * FROM replacements WHERE author_id=?", (telegram_id,))
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["active"] = bool(d.get("active", 1))
        d["confirmed"] = bool(d.get("confirmed", 0))
        result.append(d)
    return result


def get_my_responses(telegram_id: int) -> list:
    """Замены, на которые пользователь откликнулся (заявка или уже принят)."""
    with _lock:
        cur = _get_conn().execute(
            """SELECT * FROM replacements
               WHERE requested_by_id=? OR taken_by_id=?
               ORDER BY date_from DESC""",
            (telegram_id, telegram_id),
        )
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["active"] = bool(d.get("active", 1))
        d["confirmed"] = bool(d.get("confirmed", 0))
        result.append(d)
    return result


# --- Tickets ---
def get_tickets(closed: Optional[bool] = None) -> list:
    with _lock:
        if closed is None:
            cur = _get_conn().execute("SELECT * FROM tickets")
        else:
            cur = _get_conn().execute("SELECT * FROM tickets WHERE closed=?", (1 if closed else 0,))
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["closed"] = bool(d.get("closed", 0))
        if isinstance(d.get("messages"), str):
            d["messages"] = json.loads(d["messages"]) if d["messages"] else []
        result.append(d)
    return result


def get_ticket_by_id(tid: str) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute("SELECT * FROM tickets WHERE id=?", (tid,))
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["closed"] = bool(d.get("closed", 0))
    if isinstance(d.get("messages"), str):
        d["messages"] = json.loads(d["messages"]) if d["messages"] else []
    return d


def save_ticket(ticket: dict):
    with _lock:
        m = json.dumps(ticket.get("messages", []), ensure_ascii=False)
        _get_conn().execute(
            """INSERT OR REPLACE INTO tickets VALUES (?,?,?,?,?)""",
            (ticket.get("id"), ticket.get("user_id"), ticket.get("username", ""),
             m, 1 if ticket.get("closed") else 0))
        _get_conn().commit()


# --- Object shift types (per object: day/night start/end) ---
def get_object_shift(city: str, company: str, object_name: str, shift_key: str) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute(
            """SELECT * FROM object_shifts
               WHERE city=? AND company=? AND object_name=? AND shift_key=?""",
            (city, company, object_name, shift_key),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def set_object_shift(city: str, company: str, object_name: str, shift_key: str, start_time: str, end_time: str):
    with _lock:
        _get_conn().execute(
            """INSERT OR REPLACE INTO object_shifts
               (city, company, object_name, shift_key, start_time, end_time)
               VALUES (?,?,?,?,?,?)""",
            (city, company, object_name, shift_key, start_time, end_time),
        )
        _get_conn().commit()


def get_object_shifts_for_object(city: str, company: str, object_name: str) -> list:
    with _lock:
        cur = _get_conn().execute(
            """SELECT * FROM object_shifts
               WHERE city=? AND company=? AND object_name=?
               ORDER BY shift_key""",
            (city, company, object_name),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# --- Reviews ---
def get_review_by_user(user_id: int) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute(
            "SELECT * FROM reviews WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def save_review(review: dict) -> int:
    """Создать новый или обновить существующий отзыв. Возвращает id отзыва."""
    with _lock:
        if review.get("id"):
            # При редактировании пользователем не трогаем admin_reply
            _get_conn().execute(
                """UPDATE reviews
                   SET rating=?, text=?, updated_at=?
                   WHERE id=?""",
                (
                    review.get("rating"),
                    review.get("text"),
                    review.get("updated_at"),
                    review.get("id"),
                ),
            )
            _get_conn().commit()
            return int(review["id"])
        cur = _get_conn().execute(
            """INSERT INTO reviews (user_id, username, rating, text, admin_reply, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                review.get("user_id"),
                review.get("username", ""),
                review.get("rating"),
                review.get("text"),
                review.get("admin_reply"),
                review.get("created_at"),
                review.get("updated_at"),
            ),
        )
        _get_conn().commit()
        return int(cur.lastrowid)


def get_reviews(order: str = "recent", limit: int = 50, offset: int = 0) -> list:
    """order: recent | rating_asc | rating_desc."""
    if order == "rating_asc":
        order_by = "rating ASC, created_at DESC"
    elif order == "rating_desc":
        order_by = "rating DESC, created_at DESC"
    else:
        order_by = "created_at DESC"
    with _lock:
        cur = _get_conn().execute(
            f"SELECT * FROM reviews ORDER BY {order_by} LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["likes"], d["dislikes"] = _count_reactions(d["id"])
        result.append(d)
    return result


def get_reviews_count() -> int:
    with _lock:
        cur = _get_conn().execute("SELECT COUNT(*) FROM reviews")
        row = cur.fetchone()
    return int(row[0]) if row else 0


def get_reviews_avg_rating() -> float:
    with _lock:
        cur = _get_conn().execute("SELECT AVG(rating) FROM reviews")
        row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def get_review_by_id(rid: int) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute("SELECT * FROM reviews WHERE id=?", (rid,))
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["likes"], d["dislikes"] = _count_reactions(d["id"])
    return d


def delete_review(rid: int):
    with _lock:
        _get_conn().execute("DELETE FROM review_reactions WHERE review_id=?", (rid,))
        _get_conn().execute("DELETE FROM reviews WHERE id=?", (rid,))
        _get_conn().commit()


def _count_reactions(review_id: int) -> tuple[int, int]:
    with _lock:
        cur = _get_conn().execute(
            "SELECT value, COUNT(*) as c FROM review_reactions WHERE review_id=? GROUP BY value",
            (review_id,),
        )
        rows = cur.fetchall()
    likes = dislikes = 0
    for row in rows:
        if row[0] == 1:
            likes = row[1]
        elif row[0] == -1:
            dislikes = row[1]
    return likes, dislikes


def get_review_reaction(review_id: int, user_id: int) -> int:
    """Возвращает 1 (like), -1 (dislike) или 0 (нет реакции)."""
    with _lock:
        cur = _get_conn().execute(
            "SELECT value FROM review_reactions WHERE review_id=? AND user_id=?",
            (review_id, user_id),
        )
        row = cur.fetchone()
    return int(row[0]) if row else 0


def set_review_reaction(review_id: int, user_id: int, value: int):
    """value: 1 (like), -1 (dislike), 0 (удалить реакцию)."""
    with _lock:
        if value == 0:
            _get_conn().execute(
                "DELETE FROM review_reactions WHERE review_id=? AND user_id=?",
                (review_id, user_id),
            )
        else:
            _get_conn().execute(
                "INSERT OR REPLACE INTO review_reactions (review_id, user_id, value) VALUES (?,?,?)",
                (review_id, user_id, value),
            )
        _get_conn().commit()


# --- Catalog (city -> company -> object -> positions) ---
def get_cities() -> List[str]:
    with _lock:
        cur = _get_conn().execute("SELECT name FROM catalog_cities ORDER BY name")
        return [r[0] for r in cur.fetchall()]


def get_companies(city: str) -> List[str]:
    with _lock:
        cur = _get_conn().execute("SELECT name FROM catalog_companies WHERE city=? ORDER BY name", (city,))
        return [r[0] for r in cur.fetchall()]


def get_objects(city: str, company: str) -> List[str]:
    with _lock:
        cur = _get_conn().execute(
            "SELECT name FROM catalog_objects WHERE city=? AND company=? ORDER BY name",
            (city, company))
        return [r[0] for r in cur.fetchall()]


def get_positions(city: str, company: str, object_name: str) -> List[str]:
    with _lock:
        cur = _get_conn().execute(
            "SELECT name FROM catalog_positions WHERE city=? AND company=? AND object_name=? ORDER BY name",
            (city, company, object_name))
        return [r[0] for r in cur.fetchall()]


def get_all_positions() -> List[str]:
    """Все позиции во всех объектах (для фильтров уведомлений)."""
    with _lock:
        cur = _get_conn().execute("SELECT DISTINCT name FROM catalog_positions ORDER BY name")
        return [r[0] for r in cur.fetchall()]


def catalog_add_city(name: str) -> bool:
    name = name.strip()
    with _lock:
        try:
            _get_conn().execute("INSERT INTO catalog_cities VALUES (?)", (name,))
            _get_conn().commit()
            return True
        except sqlite3.IntegrityError:
            return False


def catalog_remove_city(city: str):
    with _lock:
        _get_conn().execute("DELETE FROM catalog_cities WHERE name=?", (city,))
        _get_conn().execute("DELETE FROM catalog_companies WHERE city=?", (city,))
        _get_conn().execute("DELETE FROM catalog_objects WHERE city=?", (city,))
        _get_conn().execute("DELETE FROM catalog_positions WHERE city=?", (city,))
        _get_conn().commit()


def catalog_rename_city(old: str, new: str) -> bool:
    old, new = old.strip(), new.strip()
    if not old or not new or old == new:
        return False
    with _lock:
        try:
            _get_conn().execute("UPDATE catalog_cities SET name=? WHERE name=?", (new, old))
            _get_conn().execute("UPDATE catalog_companies SET city=? WHERE city=?", (new, old))
            _get_conn().execute("UPDATE catalog_objects SET city=? WHERE city=?", (new, old))
            _get_conn().execute("UPDATE catalog_positions SET city=? WHERE city=?", (new, old))
            _get_conn().execute("UPDATE object_shifts SET city=? WHERE city=?", (new, old))
            _get_conn().execute("UPDATE object_access SET city=? WHERE city=?", (new, old))
            _get_conn().execute("UPDATE object_access_chats SET city=? WHERE city=?", (new, old))
            _get_conn().execute("UPDATE users SET city=? WHERE city=?", (new, old))
            _get_conn().execute("UPDATE replacements SET city=? WHERE city=?", (new, old))
            _get_conn().commit()
            return True
        except sqlite3.IntegrityError:
            return False


def catalog_add_company(city: str, name: str):
    with _lock:
        _get_conn().execute("INSERT OR IGNORE INTO catalog_companies VALUES (?,?)", (city, name.strip()))
        _get_conn().commit()


def catalog_rename_company(city: str, old: str, new: str) -> bool:
    old, new = old.strip(), new.strip()
    if not old or not new or old == new:
        return False
    with _lock:
        try:
            _get_conn().execute(
                "UPDATE catalog_companies SET name=? WHERE city=? AND name=?",
                (new, city, old),
            )
            _get_conn().execute("UPDATE catalog_objects SET company=? WHERE city=? AND company=?", (new, city, old))
            _get_conn().execute("UPDATE catalog_positions SET company=? WHERE city=? AND company=?", (new, city, old))
            _get_conn().execute("UPDATE object_shifts SET company=? WHERE city=? AND company=?", (new, city, old))
            _get_conn().execute("UPDATE object_access SET company=? WHERE city=? AND company=?", (new, city, old))
            _get_conn().execute("UPDATE object_access_chats SET company=? WHERE city=? AND company=?", (new, city, old))
            _get_conn().execute("UPDATE users SET company=? WHERE city=? AND company=?", (new, city, old))
            _get_conn().execute("UPDATE replacements SET company=? WHERE city=? AND company=?", (new, city, old))
            _get_conn().commit()
            return True
        except sqlite3.IntegrityError:
            return False


def catalog_add_object(city: str, company: str, name: str):
    with _lock:
        _get_conn().execute("INSERT OR IGNORE INTO catalog_objects VALUES (?,?,?)", (city, company, name.strip()))
        _get_conn().commit()


def catalog_rename_object(city: str, company: str, old: str, new: str) -> bool:
    old, new = old.strip(), new.strip()
    if not old or not new or old == new:
        return False
    with _lock:
        try:
            _get_conn().execute(
                "UPDATE catalog_objects SET name=? WHERE city=? AND company=? AND name=?",
                (new, city, company, old),
            )
            _get_conn().execute(
                "UPDATE catalog_positions SET object_name=? WHERE city=? AND company=? AND object_name=?",
                (new, city, company, old),
            )
            _get_conn().execute(
                "UPDATE object_shifts SET object_name=? WHERE city=? AND company=? AND object_name=?",
                (new, city, company, old),
            )
            _get_conn().execute(
                "UPDATE object_access SET object_name=? WHERE city=? AND company=? AND object_name=?",
                (new, city, company, old),
            )
            _get_conn().execute(
                "UPDATE object_access_chats SET object_name=? WHERE city=? AND company=? AND object_name=?",
                (new, city, company, old),
            )
            _get_conn().execute(
                "UPDATE users SET object=? WHERE city=? AND company=? AND object=?",
                (new, city, company, old),
            )
            _get_conn().execute(
                "UPDATE replacements SET object=? WHERE city=? AND company=? AND object=?",
                (new, city, company, old),
            )
            _get_conn().commit()
            return True
        except sqlite3.IntegrityError:
            return False


def catalog_add_position(city: str, company: str, object_name: str, name: str):
    with _lock:
        _get_conn().execute("INSERT OR IGNORE INTO catalog_positions VALUES (?,?,?,?)",
                            (city, company, object_name, name.strip()))
        _get_conn().commit()


def catalog_rename_position(city: str, company: str, object_name: str, old: str, new: str) -> bool:
    old, new = old.strip(), new.strip()
    if not old or not new or old == new:
        return False
    with _lock:
        try:
            _get_conn().execute(
                "UPDATE catalog_positions SET name=? WHERE city=? AND company=? AND object_name=? AND name=?",
                (new, city, company, object_name, old),
            )
            _get_conn().execute(
                "UPDATE replacements SET position=? WHERE city=? AND company=? AND object=? AND position=?",
                (new, city, company, object_name, old),
            )
            _get_conn().commit()
            return True
        except sqlite3.IntegrityError:
            return False


# --- Offers (готов выйти на замену) ---
def save_offer(offer: dict):
    with _lock:
        _get_conn().execute(
            """INSERT OR REPLACE INTO offers
               (id, author_id, author_username, city, company, object,
                positions_json, shift_key, date_from, date_to, date_text,
                pay_enabled, pay_amount_byn, active, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                offer.get("id"),
                offer.get("author_id"),
                offer.get("author_username", ""),
                offer.get("city"),
                offer.get("company"),
                offer.get("object"),
                offer.get("positions_json") or "[]",
                offer.get("shift_key"),
                offer.get("date_from"),
                offer.get("date_to"),
                offer.get("date_text"),
                1 if offer.get("pay_enabled") else 0,
                offer.get("pay_amount_byn"),
                1 if offer.get("active", True) else 0,
                offer.get("created_at"),
            ),
        )
        _get_conn().commit()


def get_offers(active_only: bool = True) -> list:
    with _lock:
        if active_only:
            cur = _get_conn().execute("SELECT * FROM offers WHERE active=1 ORDER BY created_at DESC")
        else:
            cur = _get_conn().execute("SELECT * FROM offers ORDER BY created_at DESC")
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["active"] = bool(d.get("active", 1))
        d["pay_enabled"] = bool(d.get("pay_enabled", 0))
        result.append(d)
    return result


def get_offer_by_id(oid: str) -> Optional[dict]:
    with _lock:
        cur = _get_conn().execute("SELECT * FROM offers WHERE id=?", (oid,))
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["active"] = bool(d.get("active", 1))
    d["pay_enabled"] = bool(d.get("pay_enabled", 0))
    return d


def deactivate_offer(oid: str):
    with _lock:
        _get_conn().execute("UPDATE offers SET active=0 WHERE id=?", (oid,))
        _get_conn().commit()


def get_my_offers(author_id: int, active_only: bool = True) -> list:
    with _lock:
        if active_only:
            cur = _get_conn().execute(
                "SELECT * FROM offers WHERE author_id=? AND active=1 ORDER BY created_at DESC",
                (author_id,),
            )
        else:
            cur = _get_conn().execute(
                "SELECT * FROM offers WHERE author_id=? ORDER BY created_at DESC",
                (author_id,),
            )
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["active"] = bool(d.get("active", 1))
        d["pay_enabled"] = bool(d.get("pay_enabled", 0))
        result.append(d)
    return result


def catalog_remove_company(city: str, index: int):
    companies = get_companies(city)
    if 0 <= index < len(companies):
        with _lock:
            _get_conn().execute("DELETE FROM catalog_companies WHERE city=? AND name=?", (city, companies[index]))
            _get_conn().execute("DELETE FROM catalog_objects WHERE city=? AND company=?", (city, companies[index]))
            _get_conn().execute("DELETE FROM catalog_positions WHERE city=? AND company=?", (city, companies[index]))
            _get_conn().commit()


def catalog_remove_object(city: str, company: str, index: int):
    objects = get_objects(city, company)
    if 0 <= index < len(objects):
        with _lock:
            _get_conn().execute("DELETE FROM catalog_objects WHERE city=? AND company=? AND name=?",
                                (city, company, objects[index]))
            _get_conn().execute("DELETE FROM catalog_positions WHERE city=? AND company=? AND object_name=?",
                                (city, company, objects[index]))
            _get_conn().commit()


def catalog_remove_position(city: str, company: str, object_name: str, index: int):
    positions = get_positions(city, company, object_name)
    if 0 <= index < len(positions):
        with _lock:
            _get_conn().execute("DELETE FROM catalog_positions WHERE city=? AND company=? AND object_name=? AND name=?",
                                (city, company, object_name, positions[index]))
            _get_conn().commit()
