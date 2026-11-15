import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
from bot.handlers import router
from db import Database
from nft_client import NftClient
from sniper import Sniper


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("Задайте BOT_TOKEN в .env")

    db, client = Database(), NftClient()
    await db.init()
    await client.start()

    bot = Bot(config.BOT_TOKEN)
    dp = Dispatcher(db=db)
    dp.include_router(router)

    sniper_task = asyncio.create_task(Sniper(bot, db, client).run())
    try:
        await dp.start_polling(bot)
    finally:
        sniper_task.cancel()
        await client.close()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
