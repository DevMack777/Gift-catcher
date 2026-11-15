"""Фоновая логика снайпера: каждые CHECK_INTERVAL секунд ищет новые номера."""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (TelegramAPIError, TelegramForbiddenError,
                                TelegramRetryAfter)

import config
from db import Database
from nft_client import NftClient, NftInfo

log = logging.getLogger(__name__)


def format_alert(nft: NftInfo, username: str | None, first_name: str) -> str:
    who = f"@{username}" if username else first_name
    return (
        f"🎯 <b>Новый подарок #{nft.number}</b>\n\n"
        f"· Ищущим: {who}\n"
        f"· Ссылка на NFT: <a href=\"{nft.url}\">{nft.url}</a>\n"
        f"· Модель: {nft.model}\n"
        f"· Узор: {nft.symbol}\n"
        f"· Фон: {nft.backdrop}")


class Sniper:
    def __init__(self, bot: Bot, db: Database, client: NftClient):
        self.bot, self.db, self.client = bot, db, client
        self._sem = asyncio.Semaphore(5)

    async def run(self) -> None:
        log.info("Sniper started, interval=%ss", config.CHECK_INTERVAL)
        while True:
            try:
                cols = await self.db.active_collections()
                await asyncio.gather(*(self._check(c) for c in cols))
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Sniper cycle failed")
            await asyncio.sleep(config.CHECK_INTERVAL)

    async def _check(self, col) -> None:
        slug, last = col["slug"], col["last_number"]
        async with self._sem:
            try:
                if last == 0:
                    await self._baseline(slug)
                    return
                for number in range(last + 1, last + 1 + config.MAX_NEW_PER_CYCLE):
                    nft = await self.client.fetch(slug, number)
                    if nft is None:
                        break
                    await self.db.set_last_number(slug, number)
                    await self.db.add_model(slug, nft.model)
                    await self.db.save_history(nft)
                    await self._notify(nft)
            except Exception as e:      # сеть/парсинг — не роняем остальные коллекции
                log.warning("Check %s failed: %s", slug, e)

    async def _baseline(self, slug: str) -> None:
        """Первый запуск: запоминаем текущий максимум без алертов и собираем известные модели."""
        latest = await self.client.find_latest(slug)
        if latest <= 0:
            return
        for n in range(max(1, latest - 10), latest + 1):
            nft = await self.client.fetch(slug, n)
            if nft:
                await self.db.add_model(slug, nft.model)
        await self.db.set_last_number(slug, latest)
        log.info("Baseline %s = #%s", slug, latest)

    async def _notify(self, nft: NftInfo) -> None:
        for sub in await self.db.subscribers(nft.slug):
            flt = sub["model_filter"]
            if flt and flt.lower() != nft.model.lower():
                continue
            text = format_alert(nft, sub["username"], sub["first_name"])
            try:
                await self.bot.send_message(sub["id"], text, parse_mode="HTML")
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await self.bot.send_message(sub["id"], text, parse_mode="HTML")
                except TelegramAPIError:
                    log.warning("Retry send to %s failed", sub["id"])
            except TelegramForbiddenError:
                log.info("User %s blocked the bot", sub["id"])
            except TelegramAPIError as e:
                log.warning("Send to %s failed: %s", sub["id"], e)
