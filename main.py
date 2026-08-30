import asyncio
import itertools
import os
import sys
import aiohttp
import aiosqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv
from typing import Optional
from get_commands import AllBotCommands

print("[DEBUG] main.py interpreter:", sys.executable)
print("[DEBUG] main.py sys.path[0]:", sys.path[0] if sys.path else "N/A")

load_dotenv()

ENV = os.environ.get("ENVIRONMENT", "development").lower()


class Paginator(discord.ui.View):
    def __init__(self, ctx, pages, per_page=10, title="Data List"):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.current_page = 0
        self.title = title
        self.message: Optional[discord.Message] = None

        if not pages:
            pages = ["Walo data."]

        # Check if we were passed a list of Embeds or a list of Strings
        if isinstance(pages[0], discord.Embed):
            self.pages = pages
            self.is_embed_list = True
            self.total_pages = len(self.pages)
        else:
            self.is_embed_list = False
            # Chunk string lines automatically if not already chunked
            if isinstance(pages, list) and all(isinstance(x, str) for x in pages) and len(pages) > 0 and "\n" not in pages[0]:
                self.chunks = ["\n".join(pages[i:i + per_page]) for i in range(0, len(pages), per_page)]
            else:
                self.chunks = pages
            self.total_pages = len(self.chunks)

        self._update_button_states()

    def _update_button_states(self):
        if self.total_pages <= 1:
            self.clear_items()
        else:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    if child.label == "◀️":
                        child.disabled = (self.current_page == 0)
                    elif child.label == "▶️":
                        child.disabled = (self.current_page == self.total_pages - 1)

    def get_page(self):
        if self.is_embed_list:
            embed = self.pages[self.current_page]
            embed.color = 0x000000
            if self.total_pages > 1:
                embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")
            return embed
        else:
            embed = discord.Embed(
                title=self.title,
                description=self.chunks[self.current_page],
                color=0x000000
            )
            if self.total_pages > 1:
                embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")
            return embed

    async def send(self):
        embed = self.get_page()
        self.message = await self.ctx.send(embed=embed, view=self if self.total_pages > 1 else None)
        return self.message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Mat9edch tkhdem had l buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_button_states()
            await interaction.response.edit_message(embed=self.get_page(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_button_states()
            await interaction.response.edit_message(embed=self.get_page(), view=self)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, 'message') and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


async def get_prefix(bot, message):
    if ENV == "dev":
        base_prefixes = ["dev"]
    else:
        base_prefixes = ["sat"]
        if message.guild:
            async with bot.db.execute("SELECT prefix FROM guild_prefixes WHERE guild_id = ?",
                                      (message.guild.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    base_prefixes.append(row[0])

    prefixes = []
    for bp in base_prefixes:
        variations = list(map(''.join, itertools.product(*zip(bp.upper(), bp.lower()))))
        for var in variations:
            prefixes.append(f"{var} ")
            prefixes.append(var)

    return commands.when_mentioned_or(*prefixes)(bot, message)


class HelpDropdown(discord.ui.Select):
    def __init__(self, help_command):
        self.help_command = help_command

        options = []
        for category in AllBotCommands.keys():
            options.append(discord.SelectOption(
                label=category,
                description=f"Commands ta3 {category}",
                value=category
            ))

        super().__init__(placeholder="Khtar category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.help_command.context.author.id:
            await interaction.response.send_message("Mat9edch tkhdem had l menu.", ephemeral=True)
            return

        selected_category = self.values[0]
        command_names = AllBotCommands.get(selected_category, [])

        formatted_commands = " ".join([f"`{name}`" for name in command_names])

        embed = discord.Embed(
            title=f"Category: {selected_category}",
            description=formatted_commands or "Category khawya.",
            color=0x000000
        )

        await interaction.response.edit_message(embed=embed)


class HelpDropdownView(discord.ui.View):
    def __init__(self, help_command):
        super().__init__(timeout=120)
        self.help_command = help_command
        self.add_item(HelpDropdown(help_command))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, 'message') and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class ModernHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={"help": "Katwrik ga3 l commands.",
                                        "aliases": ["mosa3ada", "3awn", "commands", "3t9",
                                                    "3te9"]})

    async def command_callback(self, ctx, *, command=None):
        if command is not None:
            matched_category = None
            for category in AllBotCommands.keys():
                if category.lower() == command.lower():
                    matched_category = category
                    break
            
            if matched_category:
                return await self.send_category_help(matched_category)
                
        return await super().command_callback(ctx, command=command)

    async def send_category_help(self, category):
        ctx = self.context
        command_names = AllBotCommands.get(category, [])
        formatted_commands = " ".join([f"`{name}`" for name in command_names])

        embed = discord.Embed(
            title=f"Category: {category}",
            description=formatted_commands or "Category khawya.",
            color=0x000000
        )
        
        view = HelpDropdownView(self)
        await ctx.send(embed=embed, view=view)

    async def send_bot_help(self, mapping):
        ctx = self.context
        total_commands = 0
        categories_summary = []

        for category, cmds in AllBotCommands.items():
            total_commands += len(cmds)
            categories_summary.append(f"**{category}** • {len(cmds)} commands")

        embed = discord.Embed(
            title=f"Ga3 l commands [{total_commands}]",
            description="\n".join(categories_summary) if categories_summary else "Walo categories.",
            color=0x000000
        )
        embed.set_footer(text="Khtar chy category bach tchouf l commands li fiha.")

        view = HelpDropdownView(self)
        view.message = await ctx.send(embed=embed, view=view)

    async def send_command_help(self, command):
        ctx = self.context
        p = ctx.clean_prefix
        aliases = f" `[{'|'.join(command.aliases)}]`" if command.aliases else ""

        embed = discord.Embed(
            title=f"Command: {command.name}{aliases}",
            description=command.help or "",
            color=0x000000
        )
        embed.add_field(
            name="Usage",
            value=f"`{p}{command.qualified_name} {command.signature}`",
            inline=False
        )
        await ctx.send(embed=embed)

    async def send_group_help(self, group):
        ctx = self.context
        p = ctx.clean_prefix

        embed = discord.Embed(
            title=f"Group: {group.name}",
            description=group.help or f"Commands ta3 `{group.name}`.",
            color=0x000000
        )

        subcommands_list = []
        for cmd in group.commands:
            if not cmd.hidden:
                subcommands_list.append(f"`{cmd.name}` - {cmd.short_doc or 'Nsit ndir liha description hh.'}")

        embed.add_field(name="Subcommands", value="\n".join(subcommands_list) if subcommands_list else "None",
                        inline=False)
        embed.add_field(name="Usage Syntax", value=f"`{p}{group.name} [subcommand]`", inline=False)
        await ctx.send(embed=embed)

    async def send_error_message(self, error):
        await self.context.send(f"Mochkil: {error}")


intents = discord.Intents.all()
intents.presences = False
intents.typing = False

bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    help_command=ModernHelpCommand(),
    case_insensitive=True,
    chunk_guilds_at_startup=False,
    member_cache_flags=discord.MemberCacheFlags(voice=True, joined=False),
    max_messages=15
)
bot.Paginator = Paginator


@bot.check
async def is_not_blacklisted(ctx):
    async with bot.db.execute("SELECT 1 FROM blacklists WHERE user_id = ?", (ctx.author.id,)) as cursor:
        is_blacklisted = await cursor.fetchone()
    return is_blacklisted is None


async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
            except Exception as e:
                print(f"Error loading cogs.{filename[:-3]}: {e}")


async def setup_hook():
    bot.session = aiohttp.ClientSession()

    # Auto-Restore from Discord backup channel if database is missing or unseeded (e.g. fresh Discloud deploy)
    backup_channel_id = os.environ.get("BACKUP_CHANNEL_ID")
    should_restore = False

    if not os.path.exists("bot_database.db"):
        should_restore = True
    else:
        try:
            import sqlite3
            test_conn = sqlite3.connect("bot_database.db")
            cur = test_conn.cursor()
            cur.execute("SELECT 1 FROM dictionary_words LIMIT 1")
            cur.fetchone()
            test_conn.close()
        except Exception:
            should_restore = True

    if should_restore and backup_channel_id:
        try:
            print(f"[Auto-Restore] Checking backup channel ID {backup_channel_id} for latest database snapshot...")
            channel = bot.get_channel(int(backup_channel_id))
            if not channel:
                channel = await bot.fetch_channel(int(backup_channel_id))

            if channel:
                async for message in channel.history(limit=30):
                    for attachment in message.attachments:
                        if attachment.filename.endswith(".zip"):
                            print(f"[Auto-Restore] Found zipped database backup {attachment.filename} ({attachment.size} bytes). Downloading & extracting...")
                            temp_zip = "temp_auto_restore.zip"
                            await attachment.save(temp_zip)
                            def _extract_zip_sync():
                                import zipfile
                                with zipfile.ZipFile(temp_zip, "r") as zf:
                                    zf.extract("bot_database.db", ".")
                            await asyncio.to_thread(_extract_zip_sync)
                            if os.path.exists(temp_zip):
                                os.remove(temp_zip)
                            print("[Auto-Restore] Successfully extracted bot_database.db from Discord zip backup!")
                            break
                        elif attachment.filename.endswith(".db"):
                            print(f"[Auto-Restore] Found database backup {attachment.filename} ({attachment.size} bytes). Downloading...")
                            await attachment.save("bot_database.db")
                            print("[Auto-Restore] Successfully restored bot_database.db from Discord backup channel!")
                            break
                    if os.path.exists("bot_database.db"):
                        try:
                            import sqlite3
                            chk_conn = sqlite3.connect("bot_database.db")
                            chk_cur = chk_conn.cursor()
                            chk_cur.execute("SELECT 1 FROM dictionary_words LIMIT 1")
                            chk_cur.fetchone()
                            chk_conn.close()
                            break
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Auto-Restore error]: {e}")

    bot.db = await aiosqlite.connect("bot_database.db")
    await bot.db.execute("PRAGMA journal_mode=WAL")
    await bot.db.execute("PRAGMA synchronous=NORMAL")
    await bot.db.execute("PRAGMA cache_size = -2000")
    await bot.db.execute("CREATE TABLE IF NOT EXISTS guild_prefixes (guild_id INTEGER PRIMARY KEY, prefix TEXT)")
    await bot.db.execute("CREATE TABLE IF NOT EXISTS blacklists (user_id INTEGER PRIMARY KEY)")
    await bot.db.execute("CREATE TABLE IF NOT EXISTS afk (user_id INTEGER PRIMARY KEY, reason TEXT, timestamp INTEGER)")
    await bot.db.execute("CREATE TABLE IF NOT EXISTS minigame_leaderboard (guild_id INTEGER, user_id INTEGER, game TEXT, wins INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id, game))")
    await bot.db.execute("CREATE TABLE IF NOT EXISTS guild_logs (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)")
    await bot.db.commit()

    await load_extensions()

    import gc
    gc.collect()

bot.setup_hook = setup_hook


async def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN missing from environment variables.")

    async with bot:
        try:
            await bot.start(token)
        finally:
            if hasattr(bot, 'db') and bot.db:
                await bot.db.close()
            if hasattr(bot, 'session') and bot.session:
                await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Click again.")