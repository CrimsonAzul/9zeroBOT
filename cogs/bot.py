import os
import psutil
import time
import zipfile
import asyncio
import discord
from discord.ext import commands, tasks
from converters import FuzzyMember


def _compress_db_snapshot_sync(source_db_path: str, target_zip_path: str):
    import gc
    with zipfile.ZipFile(target_zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(source_db_path, arcname="bot_database.db")
    gc.collect()


class Bot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_backup_db.start()

    def cog_unload(self):
        self.auto_backup_db.cancel()

    @tasks.loop(hours=6)
    async def auto_backup_db(self):
        env = os.environ.get("ENVIRONMENT", "development").lower()
        if env == "dev":
            return

        backup_channel_id = os.environ.get("BACKUP_CHANNEL_ID")
        if not backup_channel_id:
            return

        channel = self.bot.get_channel(int(backup_channel_id))
        if not channel:
            try:
                channel = await self.bot.fetch_channel(int(backup_channel_id))
            except Exception as e:
                print(f"[auto_backup_db fetch_channel error]: {e}")
                return

        if not channel or not os.path.exists("bot_database.db"):
            return

        snapshot_path = "auto_snapshot_backup.db"
        zip_path = "bot_database.db.zip"
        try:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            if os.path.exists(zip_path):
                os.remove(zip_path)

            async with self.bot.db.execute(f"VACUUM INTO '{snapshot_path}'"):
                pass

            await asyncio.to_thread(_compress_db_snapshot_sync, snapshot_path, zip_path)

            uncompressed_mb = os.path.getsize(snapshot_path) / (1024 * 1024)
            compressed_mb = os.path.getsize(zip_path) / (1024 * 1024)

            file = discord.File(zip_path, filename="bot_database.db.zip")
            embed = discord.Embed(
                title="📦 Automated Database Backup (6h)",
                description=(
                    f"• **Timestamp:** <t:{int(time.time())}:F>\n"
                    f"• **Uncompressed Size:** `{uncompressed_mb:.2f} MB`\n"
                    f"• **Compressed Zip:** `{compressed_mb:.2f} MB`\n"
                    f"• **Guilds:** `{len(self.bot.guilds)}`"
                ),
                color=0x000000
            )
            await channel.send(embed=embed, file=file)
        except Exception as e:
            print(f"[auto_backup_db error]: {e}")
        finally:
            if os.path.exists(snapshot_path):
                try:
                    os.remove(snapshot_path)
                except Exception:
                    pass
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
            import gc
            gc.collect()

    @auto_backup_db.before_loop
    async def before_auto_backup(self):
        await self.bot.wait_until_ready()
        # Wait 6 hours before the first scheduled auto backup so boot RAM stays minimal
        await asyncio.sleep(21600)


    def get_dir_size(self, path="."):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size


    @commands.command(name="usage", help="Katchouf ch7al t resources mkhdm l bot.")
    async def usage(self, ctx):
        process = psutil.Process(os.getpid())
        ram_bytes = process.memory_info().rss
        ram_mb = ram_bytes / (1024 * 1024)

        cpu_pct = psutil.cpu_percent(interval=None)

        db_path = "bot_database.db"
        db_size_mb = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0.0

        dir_size_mb = self.get_dir_size(".") / (1024 * 1024)

        embed = discord.Embed(title="System Metrics", color=0x000000)
        embed.add_field(name="Memory (RAM)", value=f"`{ram_mb:.2f} MB`", inline=True)
        embed.add_field(name="CPU Usage", value=f"`{cpu_pct:.1f}%`", inline=True)
        embed.add_field(name="Database Size", value=f"`{db_size_mb:.2f} MB`", inline=True)
        embed.add_field(name="Project Directory", value=f"`{dir_size_mb:.2f} MB`", inline=True)

        await ctx.send(embed=embed)



    @commands.command(name="servers", aliases=['guilds'], help="Servers li dakhl lihom ana.")
    async def servers(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Ma3endekch l7e9 tsta3ml had l cmd :/")
            return

        members = 0
        owners = set()
        server_lines = []

        for guild in self.bot.guilds:
            line = f"**{guild.name}** (`{guild.id}`) | `{guild.owner}` | `{guild.member_count}`"
            server_lines.append(line)
            members += guild.member_count
            if guild.owner:
                owners.add(guild.owner.id)

        if not server_lines:
            await ctx.send("Ana makayn f ta server.")
            return

        title_text = f"Servers: ({len(self.bot.guilds)}) | Owners: ({len(owners)}) | Members: ({members})"

        view = self.bot.Paginator(ctx, pages=server_lines, per_page=10, title=title_text)
        view.message = await ctx.send(embed=view.get_page(), view=view)



    @commands.command(name="inviter", help="Chkoun dkhelni l server.")
    async def inviter(self, ctx, guild_id: int):
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Ma3nkdch l7e9 tkhdm had l cmd :/")
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send("Makaynch ana fdak server.")
            return

        bot_inviter = "Unknown"
        try:
            integrations = await guild.integrations()
            for integration in integrations:
                if isinstance(integration, discord.BotIntegration):
                    if integration.application.user.id == self.bot.user.id:
                        bot_inviter = f"{integration.user.name} (`{integration.user.id}`)"
                        break
        except Exception:
            pass

        invite_url = "Ma3ndich perm bach n9ad invite."
        view = discord.ui.View()


        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).create_instant_invite:
                try:
                    invite = await channel.create_invite(max_age=300, max_uses=1)
                    invite_url = invite.url
                    view.add_item(discord.ui.Button(label="Join Server", url=invite_url, style=discord.ButtonStyle.link))
                    break
                except Exception:
                    continue

        embed = discord.Embed(title=guild.name, color=0x000000, timestamp=ctx.message.created_at)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Owner", value=f"{guild.owner} (`{guild.owner_id if guild.owner else 'Unknown'}`)", inline=False)
        embed.add_field(name="Added By", value=bot_inviter, inline=False)
        embed.add_field(name="Members", value=f"`{guild.member_count}`", inline=True)
        embed.add_field(name="Created At", value=discord.utils.format_dt(guild.created_at, style="R"), inline=True)
        embed.add_field(name="Invite Link", value=invite_url, inline=False)

        await ctx.send(embed=embed, view=view if len(view.children) > 0 else None)


    @commands.command(name="block", aliases=["blocki", "tjahl", "nkhl"], help="Manb9ach njawb khouna.")
    @commands.is_owner()
    async def block(self, ctx, user: FuzzyMember):
        async with self.bot.db.execute("SELECT 1 FROM blacklists WHERE user_id = ?", (user.id,)) as cursor:
            if await cursor.fetchone():
                await ctx.send(f"`{user}` deja blockito hh")
                return

        async with self.bot.db.execute("INSERT INTO blacklists (user_id) VALUES (?)", (user.id,)):
            await self.bot.db.commit()
        await ctx.send(f"Safi blockit `{user}`.")


    @commands.command(name="unblock", aliases=["unblocki", "tsal7"], help="Nrje3 njawb khouna.")
    @commands.is_owner()
    async def unblock(self, ctx, user: FuzzyMember):
        async with self.bot.db.execute("SELECT 1 FROM blacklists WHERE user_id = ?", (user.id,)) as cursor:
            if not await cursor.fetchone():
                await ctx.send(f"`{user}` mamblokihch aslan.")
                return

        async with self.bot.db.execute("DELETE FROM blacklists WHERE user_id = ?", (user.id,)):
            await self.bot.db.commit()
        await ctx.send(f"Safi unblockit `{user}`.")


    @commands.command(name="blacklist", aliases=["blocks", "blocklist"], help="List ta3 nas li mblocki.")
    @commands.is_owner()
    async def blacklist(self, ctx):
        async with self.bot.db.execute("SELECT user_id FROM blacklists") as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send("Mambloki ta wa7d.")
            return

        blacklist_lines = []
        for row in rows:
            user_id = row[0]
            # Try to look up username from cache, fallback to raw ID if unavailable
            user_obj = self.bot.get_user(user_id)
            if user_obj:
                blacklist_lines.append(f"• {user_obj.name} (`{user_id}`)")
            else:
                blacklist_lines.append(f"• Unknown User (`{user_id}`)")

        view = self.bot.Paginator(ctx, pages=blacklist_lines, per_page=10, title=f"Blacklist ({len(rows)})")
        view.message = await ctx.send(embed=view.get_page(), view=view)



    @commands.command(name="suggestion",aliases=["zid", "suggest"], help="Seft 9tira7 l admin.")
    async def suggestion(self, ctx, *, content: str = None):
        if content is None and not ctx.message.attachments:
            await ctx.send("Khassk tktb chi suggestion wla lo7 chi tswira/file.")
            return

        channel_id = os.getenv("SUGGESTIONS_CHANNEL_ID")
        if not channel_id:
            print("SUGGESTIONS_CHANNEL_ID is not set inside .env file.")
            return
            
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            print(f"Couldn't find suggestions channel with ID: {channel_id}")
            return

        embed = discord.Embed(
            description=content or "No content provided.",
            color=0x000000,
            timestamp=ctx.message.created_at
        )
        embed.set_author(name=f"{ctx.author} ({ctx.author.id})", icon_url=ctx.author.display_avatar.url)
        
        files = [await a.to_file() for a in ctx.message.attachments]
        await channel.send(embed=embed, files=files)
        await ctx.send("Safi wslatni suggestion ta3k, an7awlo nzidouha f a9rab wa9t inshaallah!")

    @commands.command(name="bug", aliases=["report", "9ad"],  help="Reporti chi bug l admin.")
    async def bug(self, ctx, *, content: str = None):
        if content is None and not ctx.message.attachments:
            await ctx.send("Khassk tktb chi bug wla lo7 chi tsowira/file.")
            return

        channel_id = os.getenv("BUGS_CHANNEL_ID")
        if not channel_id:
            print("BUGS_CHANNEL_ID is not set inside .env file.")
            return

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            print(f"Couldn't find bugs channel with ID: {channel_id}")
            return

        embed = discord.Embed(
            description=content or "No content provided.",
            color=0x000000,
            timestamp=ctx.message.created_at
        )
        embed.set_author(name=f"{ctx.author} ({ctx.author.id})", icon_url=ctx.author.display_avatar.url)
        
        files = [await a.to_file() for a in ctx.message.attachments]
        await channel.send(embed=embed, files=files)
        await ctx.send("Safi wselni l bug report ta3k, an9adoh f a9rab wa9t inshaallah!")

    @commands.command(name="botinfo", aliases=["info", "nta"])
    async def botinfo(self, ctx):


        total_guilds = len(self.bot.guilds)
        total_users = sum(g.member_count for g in self.bot.guilds if g.member_count)

        embed = discord.Embed(
            title=f"{self.bot.user.name}",
            description=f"Seftni lkhwadri AyouBot nkhdem blasto.\nIla khastk chy 7aja goul `{ctx.prefix}3te9`.",
            color=0x000000,
            timestamp=ctx.message.created_at
        )

        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        embed.add_field(name="Host", value=f"• **Owner:** `activif`\n• **Library:** `discord.py v{discord.__version__}`", inline=True)
        embed.add_field(name="Stats", value=f"• **Servers:** `{total_guilds}`\n• **Users:** `{total_users}`", inline=True)

        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)


        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Invite Bot",
            url="https://discord.com/oauth2/authorize?client_id=1522281059163701349&permissions=8&integration_type=0&scope=bot",
            style=discord.ButtonStyle.link
        ))
        view.add_item(discord.ui.Button(
            label="Tajda Server",
            url="https://discord.gg/QBkEfez3FJ",
            style=discord.ButtonStyle.link
        ))
        view.add_item(discord.ui.Button(
            label="GitHub Repo",
            url="https://github.com/ayoubanlouf/SifdineDiscordBot/",
            style=discord.ButtonStyle.link
        ))

        await ctx.send(embed=embed, view=view)


    @commands.command(name="backup", help="Sift backup ta3 database l DMs ta3 l owner.")
    async def backup(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Ma3endekch l7e9 tsta3ml had l cmd :/")
            return

        if not os.path.exists("bot_database.db"):
            await ctx.send("❌ Mal9itch `bot_database.db` f disk.")
            return

        wait_msg = await ctx.send("📦 Kan9ad snapshot ta3 database, sber 3lia...")
        snapshot_path = "manual_snapshot_backup.db"
        zip_path = "manual_backup.zip"
        try:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            if os.path.exists(zip_path):
                os.remove(zip_path)

            async with self.bot.db.execute(f"VACUUM INTO '{snapshot_path}'"):
                pass

            await asyncio.to_thread(_compress_db_snapshot_sync, snapshot_path, zip_path)

            uncompressed_mb = os.path.getsize(snapshot_path) / (1024 * 1024)
            compressed_mb = os.path.getsize(zip_path) / (1024 * 1024)

            file = discord.File(zip_path, filename="bot_database.db.zip")
            embed = discord.Embed(
                title="📦 Manual Database Backup",
                description=(
                    f"• **Timestamp:** <t:{int(time.time())}:F>\n"
                    f"• **Uncompressed Size:** `{uncompressed_mb:.2f} MB`\n"
                    f"• **Compressed Zip:** `{compressed_mb:.2f} MB`\n"
                    f"• **Guilds:** `{len(self.bot.guilds)}`"
                ),
                color=0x000000
            )
            await ctx.author.send(embed=embed, file=file)
            await wait_msg.edit(content="✅ Sifet lik database snapshot f DMs!")
        except Exception as e:
            await wait_msg.edit(content=f"❌ Tra mochkil f backup: `{e}`")
        finally:
            if os.path.exists(snapshot_path):
                try:
                    os.remove(snapshot_path)
                except Exception:
                    pass
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass


async def setup(bot):
    await bot.add_cog(Bot(bot))