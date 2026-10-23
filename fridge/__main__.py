import asyncio
import logging

from .bot import FridgeBot
from .config import load_config
from .storage import DutyStore


async def main() -> None:
    config = load_config()
    async with FridgeBot(config, DutyStore(config.db_path)) as bot:
        await bot.start(config.discord_token)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
