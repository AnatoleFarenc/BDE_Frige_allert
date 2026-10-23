import logging
from datetime import date, datetime

import discord
from discord.ext import commands, tasks

from .config import Config
from .storage import DutyStore

log = logging.getLogger(__name__)


def mentions(user_ids) -> str:
    return " ".join(f"<@{uid}>" for uid in sorted(user_ids))


class FridgeBot(commands.Bot):
    def __init__(self, config: Config, store: DutyStore):
        intents = discord.Intents.default()
        intents.members = True  # needed to list server members and check roles
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.config = config
        self.store = store
        self.reminder = tasks.loop(time=config.reminder_times)(self._send_reminder)

    async def setup_hook(self) -> None:
        # Imported here to avoid a circular import (web needs the bot instance).
        from .web import start_web

        await start_web(self)
        self.reminder.start()

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)
        guild = self.guild
        if guild is None:
            log.error(
                "The bot is not in the server GUILD_ID=%s. Visible servers: %s",
                self.config.guild_id, [(g.name, g.id) for g in self.guilds] or "none",
            )
        elif guild.get_role(self.config.allowed_role_id) is None:
            log.error("Role ALLOWED_ROLE_ID=%s not found in %s", self.config.allowed_role_id, guild.name)

    def today(self) -> date:
        return datetime.now(self.config.tz).date()

    @property
    def guild(self) -> discord.Guild | None:
        return self.get_guild(self.config.guild_id)

    def is_allowed(self, user_id: int) -> bool:
        guild = self.guild
        member = guild.get_member(user_id) if guild else None
        return member is not None and any(r.id == self.config.allowed_role_id for r in member.roles)

    async def _channel(self) -> discord.abc.Messageable:
        channel = self.get_channel(self.config.channel_id)
        return channel or await self.fetch_channel(self.config.channel_id)

    async def _send_reminder(self) -> None:
        user_ids = self.store.get(self.today())
        if not user_ids:
            return
        now = datetime.now(self.config.tz).time()
        times = self.config.reminder_times
        index = sum(1 for t in times if t.replace(tzinfo=None) <= now) or 1
        await (await self._channel()).send(
            f"🧊 **Fridge reminder ({index}/{len(times)})** — {mentions(user_ids)} "
            "you're on fridge cleaning duty today!"
        )

    async def notify_same_day_change(self, added: set[int], removed: set[int]) -> None:
        channel = await self._channel()
        if added:
            await channel.send(
                f"🧊 **Schedule update** — {mentions(added)} "
                "you're on fridge cleaning duty **today**!"
            )
        if removed:
            await channel.send(
                f"✅ {mentions(removed)} you're no longer on fridge duty today, you're off the hook!"
            )
