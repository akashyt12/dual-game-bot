import aiosqlite
import time
from pathlib import Path
from bot.config import DATA_DIR

DB_PATH = DATA_DIR / "bot.db"
_db = None


async def get_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(str(DB_PATH))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            name TEXT DEFAULT '',
            is_admin INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            platform TEXT DEFAULT 'jai',
            logged_in INTEGER DEFAULT 0,
            login_user TEXT DEFAULT '',
            game TEXT DEFAULT 'WinGo_30S',
            game51_type_id INTEGER DEFAULT 30,
            start_balance REAL DEFAULT 0,
            total_bet INTEGER DEFAULT 2,
            multiplier REAL DEFAULT 2.0,
            profit_target REAL DEFAULT 20.0,
            auto_restart INTEGER DEFAULT 1,
            bet_delay REAL DEFAULT 1.0,
            confidence INTEGER DEFAULT 55,
            stop_loss REAL DEFAULT 0,
            risk_level TEXT DEFAULT 'medium',
            points INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            verified_channels INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0,
            last_active REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            created_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            channel_id TEXT NOT NULL,
            invite_link TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS premium_keys (
            key TEXT PRIMARY KEY,
            hours INTEGER NOT NULL,
            created_by TEXT DEFAULT 'admin',
            created_at REAL DEFAULT 0,
            used INTEGER DEFAULT 0,
            used_by INTEGER DEFAULT 0,
            activated_at REAL DEFAULT 0,
            expires_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS statistics (
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            total_won REAL DEFAULT 0,
            total_lost REAL DEFAULT 0,
            total_bets INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            double_wins INTEGER DEFAULT 0,
            double_losses INTEGER DEFAULT 0,
            break_evens INTEGER DEFAULT 0,
            max_win_streak INTEGER DEFAULT 0,
            max_loss_streak INTEGER DEFAULT 0,
            sessions INTEGER DEFAULT 0,
            last_updated REAL DEFAULT 0,
            PRIMARY KEY(user_id, platform)
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            issue_number TEXT DEFAULT '',
            prediction_bs TEXT DEFAULT '',
            prediction_color TEXT DEFAULT '',
            actual_number INTEGER DEFAULT 0,
            actual_bs TEXT DEFAULT '',
            actual_color TEXT DEFAULT '',
            bet_amount REAL DEFAULT 0,
            result TEXT DEFAULT '',
            profit REAL DEFAULT 0,
            level INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target TEXT DEFAULT '',
            details TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );
    """)
    await db.commit()


# === User Operations ===

async def get_user(user_id: int) -> dict:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = await cursor.fetchone()
    if row:
        return dict(row)
    now = time.time()
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, created_at, last_active) VALUES (?, ?, ?)",
        (user_id, now, now)
    )
    await db.commit()
    return {"user_id": user_id, "is_admin": 0, "banned": 0, "points": 0, "platform": "jai",
            "logged_in": 0, "login_user": "", "game": "WinGo_30S", "start_balance": 0,
            "total_bet": 2, "multiplier": 2.0, "profit_target": 20.0, "auto_restart": 1,
            "bet_delay": 1.0, "confidence": 55, "stop_loss": 0, "risk_level": "medium",
            "referred_by": 0, "verified_channels": 0, "created_at": now, "last_active": now}


async def update_user(user_id: int, data: dict):
    db = await get_db()
    data["last_active"] = time.time()
    sets = ", ".join(f"{k}=?" for k in data.keys())
    vals = list(data.values()) + [user_id]
    await db.execute(f"UPDATE users SET {sets} WHERE user_id=?", vals)
    await db.commit()


async def upsert_user(user_id: int, data: dict):
    db = await get_db()
    data["user_id"] = user_id
    data["last_active"] = time.time()
    cols = ", ".join(data.keys())
    phs = ", ".join("?" for _ in data)
    await db.execute(f"INSERT OR REPLACE INTO users ({cols}) VALUES ({phs})", list(data.values()))
    await db.commit()


async def get_all_users() -> list:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_user_count() -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM users")
    row = await cursor.fetchone()
    return row[0]


async def is_admin(user_id: int) -> bool:
    from bot.config import ADMIN_IDS
    user = await get_user(user_id)
    return user_id in ADMIN_IDS or user.get("is_admin", 0) == 1


# === Channel Operations ===

async def get_channels() -> list:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM channels WHERE is_active=1 ORDER BY id")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def add_channel(name: str, channel_id: str, invite_link: str = "") -> bool:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO channels (name, channel_id, invite_link, created_at) VALUES (?, ?, ?, ?)",
            (name, channel_id, invite_link, time.time())
        )
        await db.commit()
        return True
    except Exception:
        return False


async def remove_channel(name: str) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM channels WHERE name=?", (name,))
    await db.commit()
    return cursor.rowcount > 0


# === Referral Operations ===

async def add_referral(referrer_id: int, referred_id: int) -> bool:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
            (referrer_id, referred_id, time.time())
        )
        await db.commit()
        return True
    except Exception:
        return False


async def get_referral_count(user_id: int) -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
    row = await cursor.fetchone()
    return row[0]


async def was_referred(referred_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("SELECT 1 FROM referrals WHERE referred_id=?", (referred_id,))
    return await cursor.fetchone() is not None


async def get_referrer(referred_id: int) -> int:
    db = await get_db()
    cursor = await db.execute("SELECT referrer_id FROM referrals WHERE referred_id=?", (referred_id,))
    row = await cursor.fetchone()
    return row["referrer_id"] if row else 0


# === Statistics Operations ===

async def update_stats(user_id: int, platform: str, won: float, lost: float, result: str):
    db = await get_db()
    now = time.time()
    await db.execute("""
        INSERT INTO statistics (user_id, platform, total_won, total_lost, total_bets, wins, losses,
            double_wins, double_losses, break_evens, last_updated)
        VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, platform) DO UPDATE SET
            total_won=total_won+?, total_lost=total_lost+?, total_bets=total_bets+1,
            wins=wins+?, losses=losses+?, double_wins=double_wins+?, double_losses=double_losses+?,
            break_evens=break_evens+?, last_updated=?
    """, (user_id, platform, won, lost,
          1 if won > 0 else 0, 1 if lost > 0 else 0,
          1 if result == "DOUBLE WIN" else 0, 1 if result == "DOUBLE LOSS" else 0,
          1 if result == "BREAK EVEN" else 0, now,
          won, lost,
          1 if won > 0 else 0, 1 if lost > 0 else 0,
          1 if result == "DOUBLE WIN" else 0, 1 if result == "DOUBLE LOSS" else 0,
          1 if result == "BREAK EVEN" else 0, now))
    await db.commit()


async def get_stats(user_id: int, platform: str) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM statistics WHERE user_id=? AND platform=?", (user_id, platform))
    row = await cursor.fetchone()
    return dict(row) if row else {"total_won": 0, "total_lost": 0, "total_bets": 0,
                                   "wins": 0, "losses": 0, "double_wins": 0, "double_losses": 0,
                                   "break_evens": 0}


async def add_history(user_id: int, platform: str, issue: str, pred_bs: str, pred_color: str,
                       actual_num: int, actual_bs: str, actual_color: str, bet: float,
                       result: str, profit: float, level: int):
    db = await get_db()
    await db.execute(
        """INSERT INTO history (user_id, platform, issue_number, prediction_bs, prediction_color,
            actual_number, actual_bs, actual_color, bet_amount, result, profit, level, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, platform, issue, pred_bs, pred_color, actual_num, actual_bs, actual_color,
         bet, result, profit, level, time.time()))
    await db.commit()


# === Premium Key Operations ===

async def get_key(key: str) -> dict:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM premium_keys WHERE key=?", (key,))
    row = await cursor.fetchone()
    return dict(row) if row else {}


async def use_key(key: str, user_id: int) -> bool:
    db = await get_db()
    now = time.time()
    key_data = await get_key(key)
    if not key_data or key_data.get("used"):
        return False
    hours = key_data["hours"]
    await db.execute(
        "UPDATE premium_keys SET used=1, used_by=?, activated_at=?, expires_at=? WHERE key=?",
        (user_id, now, now + hours * 3600, key))
    await db.commit()
    return True


async def save_key(key: str, hours: int):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO premium_keys (key, hours, created_at) VALUES (?, ?, ?)",
        (key, hours, time.time()))
    await db.commit()


async def get_all_keys() -> list:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM premium_keys ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_key(key: str) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM premium_keys WHERE key=?", (key,))
    await db.commit()
    return cursor.rowcount > 0


# === Admin Log ===

async def log_admin(admin_id: int, action: str, target: str = "", details: str = ""):
    db = await get_db()
    await db.execute(
        "INSERT INTO admin_logs (admin_id, action, target, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (admin_id, action, target, details, time.time()))
    await db.commit()


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
