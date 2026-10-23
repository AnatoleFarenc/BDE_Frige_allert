"""Print what the bot sees on Discord, to debug configuration: python -m fridge.check [USER_ID]"""
import asyncio
import sys

import discord

from .config import load_config


async def main(user_id: int | None) -> None:
    config = load_config()
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        print(f"Servers the bot is in: {[(g.name, g.id) for g in client.guilds] or 'none'}")
        guild = client.get_guild(config.guild_id)
        if guild is None:
            print(f"✘ GUILD_ID={config.guild_id} not found: invite the bot or fix GUILD_ID")
        else:
            print(f"✔ Server: {guild.name} ({len(guild.members)}/{guild.member_count} members cached)")
            channel = guild.get_channel(config.channel_id)
            print(f"{'✔' if channel else '✘'} CHANNEL_ID={config.channel_id}: {channel and channel.name}")
            if channel:
                perms = channel.permissions_for(guild.me)
                for name in ("view_channel", "send_messages", "read_message_history"):
                    print(f"  {'✔' if getattr(perms, name) else '✘'} bot permission {name}")
            role = guild.get_role(config.allowed_role_id)
            print(f"{'✔' if role else '✘'} ALLOWED_ROLE_ID={config.allowed_role_id}: {role and role.name}")
            if role is None:
                print("  Roles on this server:", [(r.name, r.id) for r in guild.roles])
            else:
                print("  Members with this role:", [m.display_name for m in role.members])
            if user_id:
                member = guild.get_member(user_id)
                if member is None:
                    print(f"✘ User {user_id} is not a member of {guild.name}")
                else:
                    print(f"  User {member.display_name} has roles: {[(r.name, r.id) for r in member.roles]}")
        await client.close()

    await client.start(config.discord_token)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else None))
