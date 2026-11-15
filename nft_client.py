"""Работа с сетью: получение данных об NFT-подарке по публичной странице t.me/nft."""
import asyncio
import html
import logging
import re
from dataclasses import dataclass
from typing import Optional

import aiohttp

import config

log = logging.getLogger(__name__)


@dataclass
class NftInfo:
    slug: str
    number: int
    url: str
    model: str = "—"
    backdrop: str = "—"
    symbol: str = "—"


def _field(text: str, name: str) -> Optional[str]:
    m = re.search(rf"{name}:\s*([^\n<]+)", text)
    return m.group(1).strip() if m else None


class NftClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=config.HTTP_TIMEOUT),
            headers={"User-Agent": "Mozilla/5.0 (GiftCatcher)"})

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def fetch(self, slug: str, number: int, retries: int = 2) -> Optional[NftInfo]:
        """Вернёт NftInfo, если подарок существует; None, если его ещё нет.
        Сетевые ошибки пробрасываются как aiohttp.ClientError/TimeoutError после ретраев."""
        url = config.NFT_URL.format(slug=slug, number=number)
        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                async with self._session.get(url) as resp:
                    if resp.status == 404:
                        return None
                    if resp.status != 200:
                        raise aiohttp.ClientError(f"HTTP {resp.status}")
                    page = await resp.text()
                return self._parse(slug, number, url, page)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exc = e
                await asyncio.sleep(1 + attempt)
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _parse(slug: str, number: int, url: str, page: str) -> Optional[NftInfo]:
        # Метаданные берём из og:description / тела страницы. Формат может
        # меняться — при необходимости поправьте регулярки здесь.
        text = html.unescape(page)
        model = _field(text, "Model")
        if not model:          # у несуществующих номеров характеристик нет
            return None
        return NftInfo(
            slug=slug, number=number, url=url, model=model,
            backdrop=_field(text, "Backdrop") or "—",
            symbol=_field(text, "Symbol") or "—")

    async def find_latest(self, slug: str) -> int:
        """Находит наибольший существующий номер (экспоненциальный + бинарный поиск)."""
        if not await self.fetch(slug, 1):
            return 0
        hi = 1
        while await self.fetch(slug, hi * 2):
            hi *= 2
            if hi > 5_000_000:
                break
        lo, hi = hi, hi * 2          # lo существует, hi — нет
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if await self.fetch(slug, mid):
                lo = mid
            else:
                hi = mid
        return lo
