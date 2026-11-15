import logging
from typing import Optional

import aiosqlite

import config

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, username TEXT, first_name TEXT);
CREATE TABLE IF NOT EXISTS collections(
    slug TEXT PRIMARY KEY, name TEXT NOT NULL, last_number INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS selections(
    user_id INTEGER, slug TEXT, PRIMARY KEY(user_id, slug));
CREATE TABLE IF NOT EXISTS model_filters(
    user_id INTEGER, slug TEXT, model TEXT, PRIMARY KEY(user_id, slug));
CREATE TABLE IF NOT EXISTS models(
    slug TEXT, model TEXT, PRIMARY KEY(slug, model));
CREATE TABLE IF NOT EXISTS nft_history(
    slug TEXT, number INTEGER, model TEXT, backdrop TEXT, symbol TEXT, url TEXT,
    seen_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(slug, number));
"""


class Database:
    def __init__(self, path: str = config.DB_PATH):
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        for slug, name in config.COLLECTIONS:
            await self.conn.execute(
                "INSERT OR IGNORE INTO collections(slug, name) VALUES(?,?)", (slug, name))
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def _all(self, sql: str, params=()) -> list:
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchall()

    # --- users
    async def upsert_user(self, uid: int, username: Optional[str], first_name: str) -> None:
        await self.conn.execute(
            "INSERT INTO users(id, username, first_name) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (uid, username, first_name))
        await self.conn.commit()

    # --- каталог (по алфавиту)
    async def list_collections(self, query: str = "") -> list:
        rows = await self._all("SELECT slug, name, last_number FROM collections")
        q = query.strip().lower()
        rows = [r for r in rows if not q or q in r["name"].lower() or q in r["slug"].lower()]
        return sorted(rows, key=lambda r: r["name"].lower())

    async def get_collection(self, slug: str):
        rows = await self._all("SELECT * FROM collections WHERE slug=?", (slug,))
        return rows[0] if rows else None

    # --- выбор
    async def get_selected(self, uid: int) -> list[str]:
        return [r["slug"] for r in await self._all(
            "SELECT slug FROM selections WHERE user_id=?", (uid,))]

    async def toggle(self, uid: int, slug: str) -> None:
        if slug in await self.get_selected(uid):
            await self.conn.execute("DELETE FROM selections WHERE user_id=? AND slug=?", (uid, slug))
            await self.conn.execute("DELETE FROM model_filters WHERE user_id=? AND slug=?", (uid, slug))
        else:
            await self.conn.execute("INSERT INTO selections VALUES(?,?)", (uid, slug))
        await self.conn.commit()

    async def set_many(self, uid: int, slugs: list[str], on: bool) -> None:
        for s in slugs:
            if on:
                await self.conn.execute("INSERT OR IGNORE INTO selections VALUES(?,?)", (uid, s))
            else:
                await self.conn.execute("DELETE FROM selections WHERE user_id=? AND slug=?", (uid, s))
                await self.conn.execute("DELETE FROM model_filters WHERE user_id=? AND slug=?", (uid, s))
        await self.conn.commit()

    # --- модели
    async def get_models(self, slug: str) -> list[str]:
        rows = await self._all("SELECT model FROM models WHERE slug=?", (slug,))
        return sorted((r["model"] for r in rows), key=str.lower)

    async def add_model(self, slug: str, model: str) -> None:
        await self.conn.execute("INSERT OR IGNORE INTO models VALUES(?,?)", (slug, model))
        await self.conn.commit()

    async def get_model_filter(self, uid: int, slug: str) -> Optional[str]:
        rows = await self._all(
            "SELECT model FROM model_filters WHERE user_id=? AND slug=?", (uid, slug))
        return rows[0]["model"] if rows else None

    async def set_model_filter(self, uid: int, slug: str, model: Optional[str]) -> None:
        if model is None:
            await self.conn.execute(
                "DELETE FROM model_filters WHERE user_id=? AND slug=?", (uid, slug))
        else:
            await self.conn.execute(
                "INSERT OR REPLACE INTO model_filters VALUES(?,?,?)", (uid, slug, model))
        await self.conn.commit()

    # --- снайпер
    async def active_collections(self) -> list:
        return await self._all(
            "SELECT c.slug, c.name, c.last_number FROM collections c "
            "WHERE c.slug IN (SELECT DISTINCT slug FROM selections)")

    async def subscribers(self, slug: str) -> list:
        return await self._all(
            "SELECT u.id, u.username, u.first_name, f.model AS model_filter "
            "FROM selections s JOIN users u ON u.id=s.user_id "
            "LEFT JOIN model_filters f ON f.user_id=s.user_id AND f.slug=s.slug "
            "WHERE s.slug=?", (slug,))

    async def set_last_number(self, slug: str, n: int) -> None:
        await self.conn.execute("UPDATE collections SET last_number=? WHERE slug=?", (n, slug))
        await self.conn.commit()

    async def save_history(self, nft) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO nft_history(slug, number, model, backdrop, symbol, url) "
            "VALUES(?,?,?,?,?,?)",
            (nft.slug, nft.number, nft.model, nft.backdrop, nft.symbol, nft.url))
        await self.conn.commit()
