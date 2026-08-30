import os
import io
import asyncio
from typing import Optional
import discord
from discord.ext import commands, tasks
from collections import deque
from datetime import datetime, timezone
import urllib
import difflib
import traceback

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channels: dict[int, int] = {}

        if not hasattr(bot, "snipe_cache"):
            bot.snipe_cache = {}
        if not hasattr(bot, "edit_cache"):
            bot.edit_cache = {}
        if not hasattr(bot, "reaction_cache"):
            bot.reaction_cache = {}

        self.cleanup_snipe_cache.start()

    async def cog_load(self):
        try:
            async with self.bot.db.execute("SELECT guild_id, channel_id FROM guild_logs") as cursor:
                rows = await cursor.fetchall()
                self.log_channels = {row[0]: row[1] for row in rows}
        except Exception as e:
            print(f"[Events.cog_load log_channels error]: {e}")

    async def send_log(self, guild: Optional[discord.Guild], embed: discord.Embed, files: Optional[list[discord.File]] = None):
        if not guild:
            return
        env = os.environ.get("ENVIRONMENT", "development").lower()
        if env == "dev":
            return
        channel_id = self.log_channels.get(guild.id)
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            # Channel was deleted or is inaccessible, clean up configuration
            self.log_channels.pop(guild.id, None)
            try:
                await self.bot.db.execute("DELETE FROM guild_logs WHERE guild_id = ?", (guild.id,))
                await self.bot.db.commit()
            except Exception:
                pass
            return
        try:
            if files:
                await channel.send(embed=embed, files=files)
            else:
                await channel.send(embed=embed)
        except discord.NotFound:
            # Channel was deleted on Discord
            self.log_channels.pop(guild.id, None)
            try:
                await self.bot.db.execute("DELETE FROM guild_logs WHERE guild_id = ?", (guild.id,))
                await self.bot.db.commit()
            except Exception:
                pass
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def get_audit_entry(self, guild: Optional[discord.Guild], action: discord.AuditLogAction, target_id: Optional[int] = None):
        if not guild or not guild.me.guild_permissions.view_audit_log:
            return None
        try:
            await asyncio.sleep(0.6)
            async for entry in guild.audit_logs(limit=6, action=action):
                if (datetime.now(timezone.utc) - entry.created_at).total_seconds() <= 15:
                    if target_id is None or (entry.target and entry.target.id == target_id):
                        return entry
        except Exception:
            pass
        return None

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user.name}.")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            if ctx.command.parent:
                parent_command = ctx.command.full_parent_name
                command_signature = ctx.command.signature
                correct_usage = f"{ctx.prefix}{parent_command} {ctx.command.name} {command_signature}"
            else:
                correct_usage = f"{ctx.prefix}{ctx.command.name} {ctx.command.signature}"

            aliases_str = '|'.join(ctx.command.aliases) if ctx.command.aliases else "_"
            e = discord.Embed(
                title="Khassk argument :/",
                description=f"**Dir b7al hka:** `{correct_usage}`\n**Aliases:** `[{aliases_str}]`",
                color=0x000000
            )
            await ctx.reply(embed=e)

        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.reply("Rani khdam f command okhra, sber ta tsali.")

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.author.send(f'{ctx.command} makhdamach f DMs.')
            except discord.HTTPException:
                pass

        elif isinstance(error, commands.BadArgument):
            if ctx.command.parent:
                parent_command = ctx.command.full_parent_name
                command_signature = ctx.command.signature
                correct_usage = f"{ctx.prefix}{parent_command} {ctx.command.name} {command_signature}"
            else:
                correct_usage = f"{ctx.prefix}{ctx.command.name} {ctx.command.signature}"

            aliases_str = '|'.join(ctx.command.aliases) if ctx.command.aliases else "_"
            e = discord.Embed(
                title="Argument ghalt :/",
                description=f"**Dir b7al hka:** `{correct_usage}`\n**Aliases:** `[{aliases_str}]`",
                color=0x000000
            )
            await ctx.reply(embed=e)

        elif isinstance(error, commands.DisabledCommand):
            await ctx.reply(f'**{ctx.command}** makhdamach db.')

        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply("Ma3ndkch l permissions bach tdir had lcommand.")

        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.reply("Ma3endich l permissions bach ndir had lcommand.")
        
        elif isinstance(error, commands.CommandNotFound):
            invoked_cmd = ctx.invoked_with.lower() if ctx.invoked_with else ""
            if not invoked_cmd:
                return

            all_cmd_names = []
            for cmd in self.bot.commands:
                if not cmd.hidden:
                    all_cmd_names.append(cmd.name.lower())
                    all_cmd_names.extend([a.lower() for a in cmd.aliases])

            matches = difflib.get_close_matches(invoked_cmd, all_cmd_names, n=1, cutoff=0.5)
            if matches:
                suggested = matches[0]
                await ctx.send(f"Wa9ila biti tgoul `{ctx.prefix}{suggested}`?")
            return
        else:
            traceback.print_exception(type(error), error, error.__traceback__)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        async with self.bot.db.execute("SELECT 1 FROM afk WHERE user_id = ?", (message.author.id,)) as cursor:
            if await cursor.fetchone():
                async with self.bot.db.execute("DELETE FROM afk WHERE user_id = ?", (message.author.id,)):
                    await self.bot.db.commit()
                await message.reply(f"3la slamto.", mention_author=False)

        if message.mentions:
            for mentioned in message.mentions:
                if mentioned.id == message.author.id:
                    continue

                async with self.bot.db.execute("SELECT reason, timestamp FROM afk WHERE user_id = ?",
                                               (mentioned.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        reason, ts = row[0], row[1]
                        time_tag = f"<t:{ts}:R>"
                        await message.reply(
                            f"**{mentioned.name}** mamsalich, galik \"{reason}\" ({time_tag})")

        ctx = await self.bot.get_context(message)

        if ctx.prefix and not ctx.command:
            cleaned_content = message.content.strip().lower()
            cleaned_prefix = ctx.prefix.strip().lower()

            if cleaned_content == cleaned_prefix:
                await ctx.send("libitibito")
                return

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return

        channel_id = message.channel.id
        if channel_id not in self.bot.snipe_cache:
            self.bot.snipe_cache[channel_id] = deque(maxlen=5)

        self.bot.snipe_cache[channel_id].append({
            "content": message.content,
            "author_name": message.author.name,
            "author_avatar": message.author.display_avatar.url,
            "time": message.created_at,
            "attachment": message.attachments[0].url if message.attachments else None
        })

        # Check if a moderator deleted the message
        audit_entry = await self.get_audit_entry(message.guild, discord.AuditLogAction.message_delete, target_id=message.author.id)
        deleted_by_str = ""
        if audit_entry and audit_entry.user and audit_entry.user.id != message.author.id:
            deleted_by_str = f"\n**Deleted By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)"

        # Download attachments into memory so they can be re-uploaded permanently
        discord_files = []
        if message.attachments:
            for att in message.attachments[:4]:
                try:
                    if att.size <= 8 * 1024 * 1024:
                        data = await att.read()
                        discord_files.append(discord.File(io.BytesIO(data), filename=att.filename))
                except Exception:
                    pass

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"**Author:** {message.author.mention} (`{message.author.id}`)\n**Channel:** {message.channel.mention}{deleted_by_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024], inline=False)
        if message.attachments:
            att_names = "\n".join(f"• `{att.filename}` ({att.size / 1024:.1f} KB)" for att in message.attachments[:5])
            embed.add_field(name="Attachments Preserved", value=att_names, inline=False)
        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
        await self.send_log(message.guild, embed, files=discord_files if discord_files else None)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild:
            return

        # Check if text changed OR attachments were removed
        removed_attachments = [att for att in before.attachments if att.id not in {a.id for a in after.attachments}]
        if before.content == after.content and not removed_attachments:
            return

        if before.content != after.content:
            await self.bot.process_commands(after)

        channel_id = before.channel.id
        if channel_id not in self.bot.edit_cache:
            self.bot.edit_cache[channel_id] = deque(maxlen=5)

        self.bot.edit_cache[channel_id].append({
            "old_content": before.content,
            "new_content": after.content,
            "author_name": before.author.name,
            "author_avatar": before.author.display_avatar.url,
            "time": after.edited_at or datetime.utcnow()
        })

        discord_files = []
        if removed_attachments:
            for att in removed_attachments[:4]:
                try:
                    if att.size <= 8 * 1024 * 1024:
                        data = await att.read()
                        discord_files.append(discord.File(io.BytesIO(data), filename=f"removed_{att.filename}"))
                except Exception:
                    pass

        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"**Author:** {before.author.mention} (`{before.author.id}`)\n**Channel:** {before.channel.mention}\n[Jump to Message]({after.jump_url})",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Before", value=(before.content or "_Empty_")[:1024], inline=False)
        embed.add_field(name="After", value=(after.content or "_Empty_")[:1024], inline=False)
        if removed_attachments:
            rem_names = "\n".join(f"• `{att.filename}` ({att.size / 1024:.1f} KB)" for att in removed_attachments[:5])
            embed.add_field(name="Removed Attachments Preserved", value=rem_names, inline=False)
        embed.set_author(name=before.author.name, icon_url=before.author.display_avatar.url)
        await self.send_log(before.guild, embed, files=discord_files if discord_files else None)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages or not messages[0].guild:
            return
        guild = messages[0].guild
        channel = messages[0].channel
        embed = discord.Embed(
            title="🧹 Bulk Messages Deleted (Purge)",
            description=f"**Count:** `{len(messages)}` messages\n**Channel:** {channel.mention}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if not payload.guild_id:
            return

        channel_id = payload.channel_id
        if channel_id not in self.bot.reaction_cache:
            self.bot.reaction_cache[channel_id] = deque(maxlen=5)

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id) if guild else None
        if member and member.bot:
            return

        username = member.name if member else f"User ID {payload.user_id}"
        avatar = member.display_avatar.url if member else None

        self.bot.reaction_cache[channel_id].append({
            "emoji": str(payload.emoji),
            "message_id": payload.message_id,
            "guild_id": payload.guild_id,
            "author_name": username,
            "author_avatar": avatar,
            "time": datetime.utcnow()
        })

    def cog_unload(self):
        self.cleanup_snipe_cache.cancel()

    @tasks.loop(hours=1)
    async def cleanup_snipe_cache(self):
        now = datetime.now(timezone.utc)

        # CHANGE THE 2 TO NUMBER OF INACTIVITY HOURS
        max_idle_seconds = 2 * 3600

        for channel_id in list(self.bot.snipe_cache.keys()):
            deque_entry = self.bot.snipe_cache[channel_id]
            if deque_entry:
                last_activity = deque_entry[-1]["time"]
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)

                if (now - last_activity).total_seconds() > max_idle_seconds:
                    del self.bot.snipe_cache[channel_id]
            else:
                del self.bot.snipe_cache[channel_id]

        for channel_id in list(self.bot.edit_cache.keys()):
            deque_entry = self.bot.edit_cache[channel_id]
            if deque_entry:
                last_activity = deque_entry[-1]["time"]
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)

                if (now - last_activity).total_seconds() > max_idle_seconds:
                    del self.bot.edit_cache[channel_id]
            else:
                del self.bot.edit_cache[channel_id]

        for channel_id in list(self.bot.reaction_cache.keys()):
            deque_entry = self.bot.reaction_cache[channel_id]
            if deque_entry:
                last_activity = deque_entry[-1]["time"]
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)

                if (now - last_activity).total_seconds() > max_idle_seconds:
                    del self.bot.reaction_cache[channel_id]
            else:
                del self.bot.reaction_cache[channel_id]

    @cleanup_snipe_cache.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not reaction.message.guild:
            return
        if user.bot:
            return

        message = reaction.message
        channel = message.channel
        emoji = reaction.emoji

        if emoji == "👀":
            if not message.content:
                return
            text = urllib.parse.quote(message.content, safe='')
            url = f"https://frenchnoodles.xyz/api/endpoints/awkwardmonkey?text={text}"
            await message.reply(url, mention_author=False)
        elif emoji == "🧠":
            if not message.content:
                return
            text = urllib.parse.quote(message.content, safe='')
            url = f"https://frenchnoodles.xyz/api/endpoints/changemymind?text={text}"
            await message.reply(url, mention_author=False)
        elif emoji == "🧽":
            if not message.content:
                return
            text = urllib.parse.quote(message.content, safe='')
            url = f"https://frenchnoodles.xyz/api/endpoints/spongebobburnpaper?text={text}"
            await message.reply(url, mention_author=False)
        elif emoji == "👎":
            if not message.content:
                return
            text = urllib.parse.quote(message.content, safe='')
            url = f"https://frenchnoodles.xyz/api/endpoints/worthless?text={text}"
            await message.reply(url, mention_author=False)
        elif emoji == "🚨":
            if not message.content:
                return
            text = urllib.parse.quote(message.content, safe='')
            url = f"https://frenchnoodles.xyz/api/endpoints/presidentialalert?text={text}"
            await message.reply(url, mention_author=False)
        elif emoji == "🎤":
            if not message.content:
                return
            text = urllib.parse.quote(message.content, safe='')
            url = f"https://frenchnoodles.xyz/api/endpoints/lisastage?text={text}"
            await message.reply(url, mention_author=False)
        else:
            return

    # ============ LOGGING EVENT LISTENERS ============

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        # Global Avatar Update
        if before.avatar != after.avatar:
            embed = discord.Embed(
                title="🖼️ User Avatar Updated",
                description=f"{after.mention} (`{after.id}`) bedel avatar dialo.",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            old_url = before.display_avatar.url
            new_url = after.display_avatar.url
            embed.add_field(name="Links", value=f"[Old Avatar]({old_url}) ➔ [New Avatar]({new_url})", inline=False)
            embed.set_thumbnail(url=old_url)
            embed.set_image(url=new_url)
            embed.set_author(name=after.name, icon_url=new_url)
            for guild in self.bot.guilds:
                if guild.get_member(after.id):
                    await self.send_log(guild, embed)

        # Global Name / Username Update
        if before.name != after.name or before.global_name != after.global_name:
            embed = discord.Embed(
                title="👤 User Profile Updated",
                description=f"{after.mention} (`{after.id}`)\n**Old Username:** `{before.name}` ({before.global_name or 'None'})\n**New Username:** `{after.name}` ({after.global_name or 'None'})",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_author(name=after.name, icon_url=after.display_avatar.url)
            for guild in self.bot.guilds:
                if guild.get_member(after.id):
                    await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        created_ts = int(member.created_at.timestamp())
        embed = discord.Embed(
            title="📥 Member Joined",
            description=f"{member.mention} (`{member.id}`)\n**Account Created:** <t:{created_ts}:R>\n**Member Count:** `{member.guild.member_count}`",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        joined_ts = int(member.joined_at.timestamp()) if member.joined_at else None
        joined_str = f"<t:{joined_ts}:R>" if joined_ts else "Unknown"
        roles_list = [r.mention for r in member.roles if r.name != "@everyone"]
        roles_str = ", ".join(roles_list) if roles_list else "None"

        # Check if member was kicked by a moderator
        audit_entry = await self.get_audit_entry(member.guild, discord.AuditLogAction.kick, target_id=member.id)
        if audit_entry:
            mod_str = f"\n**Kicked By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)"
            reason_str = f"\n**Reason:** `{audit_entry.reason}`" if audit_entry.reason else ""
            title = "👢 Member Kicked"
            desc = f"**User:** `{member.name}` ({member.mention})\n**ID:** `{member.id}`{mod_str}{reason_str}\n**Roles:** {roles_str}\n**Member Count:** `{member.guild.member_count}`"
        else:
            title = "📤 Member Left"
            desc = f"**User:** `{member.name}` ({member.mention})\n**ID:** `{member.id}`\n**Joined:** {joined_str}\n**Roles:** {roles_str}\n**Member Count:** `{member.guild.member_count}`"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        audit_entry = await self.get_audit_entry(guild, discord.AuditLogAction.ban, target_id=user.id)
        mod_str = f"\n**Banned By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)" if audit_entry and audit_entry.user else ""
        reason_str = f"\n**Reason:** `{audit_entry.reason}`" if audit_entry and audit_entry.reason else ""

        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"**User:** `{user.name}` ({user.mention})\n**ID:** `{user.id}`{mod_str}{reason_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        audit_entry = await self.get_audit_entry(guild, discord.AuditLogAction.unban, target_id=user.id)
        mod_str = f"\n**Unbanned By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)" if audit_entry and audit_entry.user else ""
        reason_str = f"\n**Reason:** `{audit_entry.reason}`" if audit_entry and audit_entry.reason else ""

        embed = discord.Embed(
            title="🔓 Member Unbanned",
            description=f"**User:** `{user.name}` ({user.mention})\n**ID:** `{user.id}`{mod_str}{reason_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Server Avatar Update
        if before.guild_avatar != after.guild_avatar:
            embed = discord.Embed(
                title="🖼️ Server Avatar Updated",
                description=f"{after.mention} (`{after.id}`) bedel server avatar dialo.",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            old_url = before.guild_avatar.url if before.guild_avatar else before.display_avatar.url
            new_url = after.guild_avatar.url if after.guild_avatar else after.display_avatar.url
            embed.add_field(name="Links", value=f"[Old Avatar]({old_url}) ➔ [New Avatar]({new_url})", inline=False)
            embed.set_thumbnail(url=old_url)
            embed.set_image(url=new_url)
            embed.set_author(name=after.name, icon_url=new_url)
            await self.send_log(after.guild, embed)

        # Nickname update
        if before.nick != after.nick:
            audit_entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.member_update, target_id=after.id)
            mod_str = f"\n**Changed By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user and audit_entry.user.id != after.id else ""
            embed = discord.Embed(
                title="📝 Nickname Changed",
                description=f"**Member:** {after.mention} (`{after.id}`)\n**Before:** `{before.nick or before.name}`\n**After:** `{after.nick or after.name}`{mod_str}",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=after.name, icon_url=after.display_avatar.url)
            await self.send_log(after.guild, embed)

        # Role updates
        if before.roles != after.roles:
            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            if added or removed:
                audit_entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.member_role_update, target_id=after.id)
                mod_str = f"\n**Updated By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
                lines = [f"**Member:** {after.mention} (`{after.id}`){mod_str}"]
                if added:
                    lines.append(f"➕ **Added:** {', '.join(r.mention for r in added)}")
                if removed:
                    lines.append(f"➖ **Removed:** {', '.join(r.mention for r in removed)}")
                embed = discord.Embed(
                    title="🛡️ Member Roles Updated",
                    description="\n".join(lines),
                    color=0x000000,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(name=after.name, icon_url=after.display_avatar.url)
                await self.send_log(after.guild, embed)

        # Timeout applied / removed
        if before.timed_out_until != after.timed_out_until:
            audit_entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.member_update, target_id=after.id)
            mod_str = f"\n**Moderator:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            reason_str = f"\n**Reason:** `{audit_entry.reason}`" if audit_entry and audit_entry.reason else ""

            if after.timed_out_until and after.timed_out_until > datetime.now(timezone.utc):
                ts = int(after.timed_out_until.timestamp())
                embed = discord.Embed(
                    title="⏳ Member Timed Out",
                    description=f"**Member:** {after.mention} (`{after.id}`)\n**Until:** <t:{ts}:F> (<t:{ts}:R>){mod_str}{reason_str}",
                    color=0x000000,
                    timestamp=datetime.now(timezone.utc)
                )
            else:
                embed = discord.Embed(
                    title="⏱️ Member Timeout Removed",
                    description=f"**Member:** {after.mention} (`{after.id}`){mod_str}",
                    color=0x000000,
                    timestamp=datetime.now(timezone.utc)
                )
            embed.set_author(name=after.name, icon_url=after.display_avatar.url)
            await self.send_log(after.guild, embed)

        # Server Boosting
        if before.premium_since is None and after.premium_since is not None:
            embed = discord.Embed(
                title="🚀 Server Boosted!",
                description=f"{after.mention} (`{after.id}`) 3ta boost l server! 🎉",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_thumbnail(url=after.display_avatar.url)
            await self.send_log(after.guild, embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        audit_entry = await self.get_audit_entry(after, discord.AuditLogAction.guild_update)
        mod_str = f"\n**Updated By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""

        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` ➔ `{after.name}`")
        if before.icon != after.icon:
            changes.append(f"**Icon:** [Old Icon]({before.icon.url if before.icon else ''}) ➔ [New Icon]({after.icon.url if after.icon else ''})")
        if before.banner != after.banner:
            changes.append(f"**Banner:** [Old]({before.banner.url if before.banner else ''}) ➔ [New]({after.banner.url if after.banner else ''})")
        if before.vanity_url_code != after.vanity_url_code:
            changes.append(f"**Vanity URL:** `{before.vanity_url_code}` ➔ `{after.vanity_url_code}`")

        if changes:
            embed = discord.Embed(
                title="🏠 Server Settings Updated",
                description="\n".join(changes) + mod_str,
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
            await self.send_log(after, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        # Joined VC
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="🔊 Voice Channel Joined",
                description=f"{member.mention} (`{member.id}`) dkhl l **{after.channel.name}** ({after.channel.mention})",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            await self.send_log(member.guild, embed)

        # Left VC
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="🔇 Voice Channel Left",
                description=f"{member.mention} (`{member.id}`) khrj mn **{before.channel.name}** ({before.channel.mention})",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            await self.send_log(member.guild, embed)

        # Moved VC
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            embed = discord.Embed(
                title="🔀 Voice Channel Moved",
                description=f"{member.mention} (`{member.id}`) t7wel mn **{before.channel.name}** ➔ **{after.channel.name}**",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            await self.send_log(member.guild, embed)

        # Server Muted / Deafened by moderator
        if before.mute != after.mute:
            audit_entry = await self.get_audit_entry(member.guild, discord.AuditLogAction.member_update, target_id=member.id)
            mod_str = f"\n**Moderator:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            status_str = "Server Muted" if after.mute else "Server Unmuted"
            embed = discord.Embed(
                title=f"🎙️ Voice {status_str}",
                description=f"**Member:** {member.mention} (`{member.id}`)\n**Action:** `{status_str}`{mod_str}",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            await self.send_log(member.guild, embed)

        if before.deaf != after.deaf:
            audit_entry = await self.get_audit_entry(member.guild, discord.AuditLogAction.member_update, target_id=member.id)
            mod_str = f"\n**Moderator:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            status_str = "Server Deafened" if after.deaf else "Server Undeafened"
            embed = discord.Embed(
                title=f"🎧 Voice {status_str}",
                description=f"**Member:** {member.mention} (`{member.id}`)\n**Action:** `{status_str}`{mod_str}",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            await self.send_log(member.guild, embed)

        # Video / Streaming started
        if not before.self_stream and after.self_stream:
            embed = discord.Embed(
                title="📺 Screen Share Started",
                description=f"{member.mention} (`{member.id}`) bda streaming f **{after.channel.name}**",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            await self.send_log(member.guild, embed)

        if not before.self_video and after.self_video:
            embed = discord.Embed(
                title="📹 Camera Turned On",
                description=f"{member.mention} (`{member.id}`) ch3l camera f **{after.channel.name}**",
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
            await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        audit_entry = await self.get_audit_entry(channel.guild, discord.AuditLogAction.channel_create, target_id=channel.id)
        mod_str = f"\n**Created By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)" if audit_entry and audit_entry.user else ""

        embed = discord.Embed(
            title="📁 Channel Created",
            description=f"**Name:** {channel.name} ({channel.mention})\n**Type:** `{str(channel.type).capitalize()}`\n**ID:** `{channel.id}`{mod_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        # If the deleted channel was the configured log channel, remove it from config
        if channel.guild and self.log_channels.get(channel.guild.id) == channel.id:
            self.log_channels.pop(channel.guild.id, None)
            try:
                await self.bot.db.execute("DELETE FROM guild_logs WHERE guild_id = ?", (channel.guild.id,))
                await self.bot.db.commit()
            except Exception as e:
                print(f"[on_guild_channel_delete cleanup error]: {e}")
            return

        audit_entry = await self.get_audit_entry(channel.guild, discord.AuditLogAction.channel_delete, target_id=channel.id)
        mod_str = f"\n**Deleted By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)" if audit_entry and audit_entry.user else ""

        embed = discord.Embed(
            title="🗑️ Channel Deleted",
            description=f"**Name:** `#{channel.name}`\n**Type:** `{str(channel.type).capitalize()}`\n**ID:** `{channel.id}`{mod_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `#{before.name}` ➔ `#{after.name}`")
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                changes.append(f"**Topic:** `{before.topic or 'None'}` ➔ `{after.topic or 'None'}`")
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"**Slowmode:** `{before.slowmode_delay}s` ➔ `{after.slowmode_delay}s`")

        if changes:
            audit_entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.channel_update, target_id=after.id)
            mod_str = f"\n**Updated By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            embed = discord.Embed(
                title="📁 Channel Updated",
                description=f"**Channel:** {after.mention}\n" + "\n".join(changes) + mod_str,
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            await self.send_log(after.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        audit_entry = await self.get_audit_entry(role.guild, discord.AuditLogAction.role_create, target_id=role.id)
        mod_str = f"\n**Created By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)" if audit_entry and audit_entry.user else ""

        embed = discord.Embed(
            title="🎭 Role Created",
            description=f"**Role:** {role.mention} (`{role.name}`)\n**ID:** `{role.id}`{mod_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        audit_entry = await self.get_audit_entry(role.guild, discord.AuditLogAction.role_delete, target_id=role.id)
        mod_str = f"\n**Deleted By:** {audit_entry.user.mention} (`{audit_entry.user.id}`)" if audit_entry and audit_entry.user else ""

        embed = discord.Embed(
            title="🗑️ Role Deleted",
            description=f"**Role:** `{role.name}`\n**ID:** `{role.id}`{mod_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` ➔ `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` ➔ `{after.color}`")
        if before.permissions != after.permissions:
            added_p = [p.replace('_', ' ').title() for p, v in after.permissions if v and not getattr(before.permissions, p)]
            removed_p = [p.replace('_', ' ').title() for p, v in before.permissions if v and not getattr(after.permissions, p)]
            if added_p:
                changes.append(f"➕ **Permissions Added:** {', '.join(added_p[:5])}")
            if removed_p:
                changes.append(f"➖ **Permissions Removed:** {', '.join(removed_p[:5])}")

        if changes:
            audit_entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.role_update, target_id=after.id)
            mod_str = f"\n**Updated By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            embed = discord.Embed(
                title="🎭 Role Updated",
                description=f"**Role:** {after.mention}\n" + "\n".join(changes) + mod_str,
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            await self.send_log(after.guild, embed)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        embed = discord.Embed(
            title="🧵 Thread Created",
            description=f"**Thread:** {thread.mention} (`{thread.name}`)\n**Channel:** {thread.parent.mention if thread.parent else 'Unknown'}\n**Creator:** {thread.owner.mention if thread.owner else 'Unknown'}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(thread.guild, embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        embed = discord.Embed(
            title="🗑️ Thread Deleted",
            description=f"**Thread Name:** `{thread.name}`\n**Channel:** {thread.parent.mention if thread.parent else 'Unknown'}\n**ID:** `{thread.id}`",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        await self.send_log(thread.guild, embed)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        max_uses = invite.max_uses if invite.max_uses > 0 else "Unlimited"
        inviter_str = invite.inviter.mention if invite.inviter else "Unknown"
        channel_str = invite.channel.mention if invite.channel else "Unknown"
        embed = discord.Embed(
            title="🔗 Invite Created",
            description=f"**Code:** [{invite.code}]({invite.url})\n**Inviter:** {inviter_str}\n**Channel:** {channel_str}\n**Max Uses:** `{max_uses}`",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        if invite.guild:
            await self.send_log(invite.guild, embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        channel_str = invite.channel.mention if invite.channel else "Unknown"
        embed = discord.Embed(
            title="🗑️ Invite Deleted",
            description=f"**Code:** `{invite.code}`\n**Channel:** {channel_str}",
            color=0x000000,
            timestamp=datetime.now(timezone.utc)
        )
        if invite.guild:
            await self.send_log(invite.guild, embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]):
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]

        if added:
            audit_entry = await self.get_audit_entry(guild, discord.AuditLogAction.emoji_create)
            mod_str = f"\n**Uploaded By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            lines = [f"{e} `:{e.name}:`" for e in added]
            embed = discord.Embed(
                title="😀 Emoji Added",
                description="\n".join(lines) + mod_str,
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            if added:
                embed.set_thumbnail(url=added[0].url)
            await self.send_log(guild, embed)

        if removed:
            audit_entry = await self.get_audit_entry(guild, discord.AuditLogAction.emoji_delete)
            mod_str = f"\n**Deleted By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            lines = [f"`:{e.name}:` (`{e.id}`)" for e in removed]
            embed = discord.Embed(
                title="🗑️ Emoji Deleted",
                description="\n".join(lines) + mod_str,
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before: list[discord.GuildSticker], after: list[discord.GuildSticker]):
        added = [s for s in after if s not in before]
        removed = [s for s in before if s not in after]

        if added:
            audit_entry = await self.get_audit_entry(guild, discord.AuditLogAction.sticker_create)
            mod_str = f"\n**Created By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            lines = [f"**{s.name}** (`{s.id}`)" for s in added]
            embed = discord.Embed(
                title="🏷️ Sticker Added",
                description="\n".join(lines) + mod_str,
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            if added:
                embed.set_thumbnail(url=added[0].url)
            await self.send_log(guild, embed)

        if removed:
            audit_entry = await self.get_audit_entry(guild, discord.AuditLogAction.sticker_delete)
            mod_str = f"\n**Deleted By:** {audit_entry.user.mention}" if audit_entry and audit_entry.user else ""
            lines = [f"**{s.name}** (`{s.id}`)" for s in removed]
            embed = discord.Embed(
                title="🗑️ Sticker Deleted",
                description="\n".join(lines) + mod_str,
                color=0x000000,
                timestamp=datetime.now(timezone.utc)
            )
            await self.send_log(guild, embed)


async def setup(bot):
    await bot.add_cog(Events(bot))
