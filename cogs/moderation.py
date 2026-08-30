from PIL import Image
from typing import Optional
import discord
from discord.ext import commands
import os
import aiohttp
import io
import random
import re
import datetime
import traceback
from converters import FuzzyMember


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ENV = os.getenv("ENVIRONMENT")
        self.fallback_emojis = ["😀", "😎", "🔥", "✨", "👑", "🎨", "👾", "⭐", "🎉", "🚀"]

    @staticmethod
    def parse_duration(duration_str: str) -> datetime.timedelta | None:
        if not duration_str:
            return None
        time_dict = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        unit = duration_str[-1].lower()
        if unit not in time_dict:
            return None
        try:
            val = int(duration_str[:-1])
            return datetime.timedelta(seconds=val * time_dict[unit])
        except ValueError:
            return None


    @commands.command(name="clearsnipes", aliases=["cs"], help="Mse7 l cache tl messagat li tms7o.")
    @commands.has_permissions(manage_messages=True)
    async def clearsnipes(self, ctx):
        cache = getattr(self.bot, "snipe_cache", {})
        channel_id = ctx.channel.id

        if channel_id in cache:
            del cache[channel_id]
        await ctx.message.add_reaction("✅")

    @commands.command(name="cleareditsnipes", aliases=["ces"], help="Mse7 l cache tl messagat li t editaw.")
    @commands.has_permissions(manage_messages=True)
    async def cleareditsnipes(self, ctx):
        cache = getattr(self.bot, "edit_cache", {})
        channel_id = ctx.channel.id

        if channel_id in cache:
            del cache[channel_id]
        await ctx.message.add_reaction("✅")

    @commands.command(name="clearreactionsnipes", aliases=["crs"], help="Mse7 l cache t reactions li t7ydo.")
    @commands.has_permissions(manage_messages=True)
    async def clearreactionsnipes(self, ctx):
        cache = getattr(self.bot, "reaction_cache", {})
        channel_id = ctx.channel.id

        if channel_id in cache:
            del cache[channel_id]
        await ctx.message.add_reaction("✅")

    @commands.command(name="clearallsnipes", aliases=["cac"], help="Mse7 l cache kaml.")
    @commands.has_permissions(manage_messages=True)
    async def clearallsnipes(self, ctx):
        channel_id = ctx.channel.id

        for cache_name in ["snipe_cache", "edit_cache", "reaction_cache"]:
            cache = getattr(self.bot, cache_name, {})
            if channel_id in cache:
                del cache[channel_id]

        await ctx.message.add_reaction("✅")

    @commands.command(name="prefix", help="Chouf l prefix li khdam wla zid wa7d jdid.")
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx, new_prefix: str = None):
        if not ctx.guild:
            await ctx.send("Had lcommand khdama gher fservers.")
            return


        async with self.bot.db.execute("SELECT prefix FROM guild_prefixes WHERE guild_id = ?",
                                       (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()
            existing_custom_prefix = row[0] if row else None


        if not new_prefix:
            current_allowed = ["sat", "ahya"] if self.ENV != "dev" else ["dev"]
            if existing_custom_prefix:
                current_allowed.append(existing_custom_prefix)

            display_list = ", ".join([f"`{p}`" for p in current_allowed])

            msg_action = f"Bach tzid custom prefix, ktb: `{ctx.prefix}prefix [custom_prefix]`"
            if existing_custom_prefix:
                msg_action += f"\n*Bach t7yed `{existing_custom_prefix}`, ktb: `{ctx.prefix}prefix {existing_custom_prefix}`"

            await ctx.send(f"Prefixes ta3 had server: {display_list}\n{msg_action}")
            return



        if new_prefix.lower() in ["sat", "ahya", "dev"]:
            await ctx.send(f"`{new_prefix}` rah default prefix mat9dch t7ydo.")
            return


        if existing_custom_prefix and new_prefix == existing_custom_prefix:
            async with self.bot.db.execute("DELETE FROM guild_prefixes WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                await self.bot.db.commit()
            await ctx.send(f"Safi lprefix `{new_prefix}` rah t7yed.")
            return


        if len(new_prefix) > 5:
            await ctx.send(embed=discord.Embed(description="Prefix khso mayfoutch 5 characters.", color=0x000000))
            return


        async with self.bot.db.execute(
                """
                INSERT INTO guild_prefixes (guild_id, prefix) 
                VALUES (?, ?)
                ON CONFLICT(guild_id) 
                DO UPDATE SET prefix = excluded.prefix
                """,
                (ctx.guild.id, new_prefix)
        ) as cursor:
            await self.bot.db.commit()

        await ctx.send(f"Safi l prefix `{new_prefix}` rah tzad.")

    @commands.command(aliases=['clear', 'mse7', 'c'])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount=1, user: FuzzyMember = None):
        amount = amount
        if amount > 100:
            await ctx.send('Lmax tl messagat li t9ed tmse7 howa 100.')
        else:
            if user == None:
                await ctx.channel.purge(limit=amount + 1)
                await ctx.send(f'Mse7t **{amount}** messages', delete_after=5)
            else:
                def is_user(m):
                    return m.author == user

                await ctx.channel.purge(limit=amount + 1, check=is_user)
                await ctx.send(f'Mse7t **{amount}** messages ta3 **{user}**', delete_after=5)

    @commands.group(name="role", help="Ga3 l commands ta3 roles.", invoke_without_command=True)
    async def role(self, ctx):
        await ctx.send(f"Hada command group. Kteb `{ctx.prefix}help role` bach tchouf subcommands.")

    @role.command(aliases=["g", "add"], help="3ti chy role l chy wa7d.")
    @commands.has_permissions(manage_roles=True)
    async def give(self, ctx, member: FuzzyMember, role: discord.Role):
        if role in member.roles:
            e = discord.Embed(description=f'{member.mention} deja 3endo {role.mention}',
                               color=0x000000)
            await ctx.send(embed=e)
        else:
            await member.add_roles(role)
            await ctx.send(embed=discord.Embed(description=f'Sf 3tit {role.mention} l {member.mention}',
                                                color=0x000000))

    @role.command(aliases=["t", "remove"], help="7yed chy role l chy wa7d.")
    @commands.has_permissions(manage_roles=True)
    async def take(self, ctx, member: FuzzyMember, role: discord.Role):
        if role in member.roles:
            await member.remove_roles(role)
            e = discord.Embed(description=f'Sf 7yet {role.mention} l {member.mention}',
                               color=0x000000)
            await ctx.send(embed=e)
        else:
            await ctx.send(embed=discord.Embed(description=f'{member.mention} ma3endoch {role.mention} aslan.',
                                                color=0x000000))

    @role.command(aliases=["l"], help="Chouf ga3 roles ta3 server.")
    @commands.has_permissions(manage_roles=True)
    async def list(self, ctx):
        if not ctx.guild:
            await ctx.send("Had lcommand khdama gher fservers.")
            return

        roles = [role for role in reversed(ctx.guild.roles) if not role.is_default()]

        if not roles:
            await ctx.send("Server mafih 7ta chi role.")
            return

        role_strings = [f"• {role.mention} ({len(role.members)} members) — `{role.id}`" for role in roles]

        view = self.bot.Paginator(
            ctx,
            pages=role_strings,
            per_page=10,
            title=f"List t roles ta3 {ctx.guild.name}"
        )
        initial_embed = view.get_page()
        msg = await ctx.send(embed=initial_embed, view=view)
        view.message = msg

    @role.command(aliases=["m"], help="Chouf members ta3 chy role.")
    @commands.has_permissions(manage_roles=True)
    async def members(self, ctx, role: discord.Role):
        if not ctx.guild:
            await ctx.send("Had lcommand khdama gher fservers.")
            return

        members = role.members

        if not members:
            await ctx.send(f"Role {role.mention} mafih ta member.")
            return

        member_strings = [f"• {member.mention} — `{member.id}`" for member in members]

        view = self.bot.Paginator(
            ctx,
            pages=member_strings,
            per_page=10,
            title=f"Members ta3 {role.name}"
        )
        initial_embed = view.get_page()
        msg = await ctx.send(embed=initial_embed, view=view)
        view.message = msg
    
    @role.command(aliases=["n"], help="Bdel smiya ta3 chy role.")
    @commands.has_permissions(manage_roles=True)
    async def name(self, ctx, role:discord.Role, *,name:str):
        await role.edit(name=name)
        e = discord.Embed(description=f"Bdelt smyt role: {role.mention}",
                           color=role.color)
        await ctx.send(embed=e)

    @role.command(aliases=["c", "colour"], help="Bdel loun ta3 chy role.")
    @commands.has_permissions(manage_roles=True)
    async def color(self, ctx, role: discord.Role, *, color:discord.Color):
        await role.edit(color=color)
        e = discord.Embed(description=f"Bdelt loun ta3 role: {role.mention}",
                           color=role.color)
        await ctx.send(embed=e)

    @role.command(aliases=["i"], help="Bdel l icon ta3 chy role.")
    @commands.has_permissions(manage_roles=True)
    async def icon(self, ctx, role: discord.Role, *, image_or_emoji:str=None):
        async def get_image_from_url(url: str):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()

        if image_or_emoji == None:
            icon_url = ctx.message.attachments[0].url
            thumbnail = icon_url
            icon = await get_image_from_url(icon_url)
        else:
            if "http" in image_or_emoji:
                thumbnail = image_or_emoji
                icon = await get_image_from_url(image_or_emoji)
            else:
                icoon = discord.PartialEmoji.from_str(image_or_emoji).url
                thumbnail = icoon
                icon = await get_image_from_url(icoon)
        await role.edit(display_icon=icon)
        e = discord.Embed(description=f"Bdelt l icon ta3 role: {role.mention}",
                           color=role.color)
        e.set_thumbnail(url=thumbnail)
        await ctx.send(embed=e)

    @commands.group(name="sticker", invoke_without_command=True, help="Ga3 l commands ta3 stickers.")
    async def sticker(self, ctx):
        await ctx.send(f"Hada command group. Kteb `{ctx.prefix}help sticker` bach tchouf subcommands.")

    @sticker.command(name="add", aliases=["a"], help="Zid sticker l server")
    @commands.has_permissions(manage_expressions=True)
    async def sticker_add(self, ctx, *, name: str=None):
        if not ctx.message.attachments:
            await ctx.send("Khsek tsift tswira m3a lcommand.")
            return

        attachment = ctx.message.attachments[0]
        emoji = random.choice(self.fallback_emojis)

        try:
            file_bytes = await attachment.read()
            img = Image.open(io.BytesIO(file_bytes))
            img = img.resize((320, 320), Image.Resampling.LANCZOS)
            
            out_io = io.BytesIO()
            img.save(out_io, format="PNG")
            out_io.seek(0)
            
            file_obj = discord.File(out_io, filename="sticker.png")

            sticker = await ctx.guild.create_sticker(
                name=name if name is not None else f"Sticker{random.randint(0, 9999)}",
                description="Custom Sticker",
                emoji=emoji,
                file=file_obj
            )

            em = discord.Embed(title="Sticker tzad!", description=f"**Name:** {sticker.name}\n**ID:** `{sticker.id}`",
                               color=0x000000)

            em.set_thumbnail(url=sticker.url)
            await ctx.send(embed=em)

        except Exception as e:
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"Tra chy mochkil :/ `{e}`", color=0x000000))

    @sticker.command(name="remove", aliases=["delete", "r", "d"], help="7yed chy sticker mn server")
    @commands.has_permissions(manage_expressions=True)
    async def sticker_remove(self, ctx, sticker_id: int = None):
        try:
            if sticker_id:
                sticker = await self.bot.fetch_sticker(sticker_id)
            elif ctx.message.stickers:
                sticker = await self.bot.fetch_sticker(ctx.message.stickers[0].id)
            else:
                await ctx.send("3tini chy sticker li bghitini n7yed wla l ID ta3o.")
                return

            em = discord.Embed(title="Sticker t7yed!",
                               description=f"**Name:** {sticker.name}\n**ID:** `{sticker.id}`", color=0x000000)
            if sticker.url:
                em.set_thumbnail(url=sticker.url)

            await sticker.delete()
            await ctx.send(embed=em)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"Mal9itch had sticker oula ma3ndich permission :/ `{e}`",
                                               color=0x000000))

    @sticker.command(name="steal", aliases=["s"], help="Chfer chy sticker mn chy server akhor.")
    @commands.has_permissions(manage_expressions=True)
    async def sticker_steal(self, ctx):
        target_stickers = []

        if ctx.message.stickers:
            target_stickers = ctx.message.stickers
        elif ctx.message.reference:
            try:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref_msg.stickers:
                    target_stickers = ref_msg.stickers
            except Exception:
                pass

        if not target_stickers:
            async for msg in ctx.channel.history(limit=20):
                if msg.id == ctx.message.id:
                    continue
                if msg.stickers:
                    target_stickers = msg.stickers
                    break

        if not target_stickers:
            await ctx.send("Sift wla replyi l sticker li bghitini nchfer.")
            return

        for target_sticker in target_stickers:
            emoji = random.choice(self.fallback_emojis)

            try:
                try:
                    async with self.bot.session.get(target_sticker.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10) as resp:
                        if resp.status == 200:
                            file_bytes = await resp.read()
                        else:
                            file_bytes = await target_sticker.read()
                except Exception:
                    file_bytes = await target_sticker.read()
                
                img = Image.open(io.BytesIO(file_bytes))
                img = img.resize((320, 320), Image.Resampling.LANCZOS)
                
                out_io = io.BytesIO()
                img.save(out_io, format="PNG")
                out_io.seek(0)
                
                file_obj = discord.File(out_io, filename="sticker.png")

                created_sticker = await ctx.guild.create_sticker(
                    name=target_sticker.name,
                    description="Stolen sticker",
                    emoji=emoji,
                    file=file_obj
                )

                em = discord.Embed(title="Sticker Tzad!",
                                   description=f"**Name:** {created_sticker.name}\n**ID:** `{created_sticker.id}`",
                                   color=0x000000)
                em.set_thumbnail(url=created_sticker.url)
                await ctx.send(embed=em, stickers=[created_sticker])
            except Exception as e:
                traceback.print_exc()
                await ctx.send(
                    embed=discord.Embed(description=f"Ma9dertch nchfer sticker **{target_sticker.name}** :/ `{e}`",
                                        color=0x000000))

    @sticker.command(name="zoom", aliases=["z"], help="Chouf tswira ta3 chy sticker")
    async def sticker_zoom(self, ctx, sticker_id: int = None):
        try:
            sticker = None
            if sticker_id:
                try:
                    sticker = await self.bot.fetch_sticker(sticker_id)
                except discord.NotFound:
                    class MockSticker:
                        def __init__(self, id_):
                            self.id = id_
                            self.name = f"Sticker {id_}"
                            self.url = f"https://cdn.discordapp.com/stickers/{id_}.png"
                    sticker = MockSticker(sticker_id)
            elif ctx.message.stickers:
                try:
                    sticker = await self.bot.fetch_sticker(ctx.message.stickers[0].id)
                except discord.NotFound:
                    sticker = ctx.message.stickers[0]
            elif ctx.message.reference:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref_msg.stickers:
                    try:
                        sticker = await self.bot.fetch_sticker(ref_msg.stickers[0].id)
                    except discord.NotFound:
                        sticker = ref_msg.stickers[0]

            if not sticker:
                async for msg in ctx.channel.history(limit=20):
                    if msg.id == ctx.message.id:
                        continue
                    if msg.stickers:
                        try:
                            sticker = await self.bot.fetch_sticker(msg.stickers[0].id)
                        except discord.NotFound:
                            sticker = msg.stickers[0]
                        break

            if not sticker:
                await ctx.send("3tini sticker li bghitini nzoomi wla replyi l chy message fih sticker.")
                return

            em = discord.Embed(
                title=f"Zoom: {sticker.name}",
                description=f"**ID:** `{sticker.id}`",
                color=0x000000
            )

            em.set_image(url=sticker.url)

            await ctx.send(embed=em)

        except Exception as e:
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"Mal9itch had sticker :/ `{e}`", color=0x000000))

    @commands.group(name="emoji", invoke_without_command=True, help="Ga3 l commands ta3 emojis.")
    async def emoji(self, ctx):
        await ctx.send(f"Hada command group. Kteb `{ctx.prefix}help emoji` bach tchouf subcommands.")

    @emoji.command(name="add", aliases=["a"], help="Zid emoji l server")
    @commands.has_permissions(manage_expressions=True)
    async def emoji_add(self, ctx, name: str = None):
        if not ctx.message.attachments:
            await ctx.send("Khsek tsift tswira m3a lcommand.")
            return

        if not name:
            name = f"Emoji{random.randint(0, 99999)}"

        attachment = ctx.message.attachments[0]
        file_bytes = await attachment.read()

        try:
            created_emoji = await ctx.guild.create_custom_emoji(
                name=name,
                image=file_bytes
            )

            em = discord.Embed(
                title="Emoji tzad!",
                description=f"**Name:** {created_emoji.name}\n**ID:** `{created_emoji.id}`\n**Emoji:** {created_emoji}",
                color=0x000000
            )
            em.set_thumbnail(url=created_emoji.url)
            await ctx.send(embed=em)

        except Exception as e:
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"Tra chy mochkil :/ `{e}`", color=0x000000))

    @emoji.command(name="remove", aliases=["delete", "r", "d"], help="7yed chy emoji mn server")
    @commands.has_permissions(manage_expressions=True)
    async def emoji_remove(self, ctx, emoji: discord.Emoji = None):
        if not emoji:
            await ctx.send("3tini chy emoji li bghitini n7yed wla l ID/Name ta3o.")
            return

        try:
            em = discord.Embed(
                title="Emoji t7yed!",
                description=f"**Name:** {emoji.name}\n**ID:** `{emoji.id}`",
                color=0x000000
            )
            em.set_thumbnail(url=emoji.url)

            await emoji.delete()
            await ctx.send(embed=em)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"Mal9itch had l emoji oula ma3ndich permission :/ `{e}`",
                                               color=0x000000))

    @emoji.command(name="steal", aliases=["s"], help="Chfer chy emoji mn chy server akhor.")
    @commands.has_permissions(manage_expressions=True)
    async def emoji_steal(self, ctx, emoji: discord.PartialEmoji = None):

        if not emoji and ctx.message.reference:
            try:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)

                custom_emoji_match = re.search(r'<(a?):([a-zA-Z0-9_]+):([0-9]+)>', ref_msg.content)
                if custom_emoji_match:
                    animated = bool(custom_emoji_match.group(1))
                    name = custom_emoji_match.group(2)
                    emoji_id = int(custom_emoji_match.group(3))
                    emoji = discord.PartialEmoji(animated=animated, name=name, id=emoji_id)
            except Exception:
                pass

        if not emoji and ctx.message.content:
            custom_emoji_match = re.search(r'<(a?):([a-zA-Z0-9_]+):([0-9]+)>', ctx.message.content)
            if custom_emoji_match:
                animated = bool(custom_emoji_match.group(1))
                name = custom_emoji_match.group(2)
                emoji_id = int(custom_emoji_match.group(3))
                emoji = discord.PartialEmoji(animated=animated, name=name, id=emoji_id)

        if not emoji:
            async for msg in ctx.channel.history(limit=20):
                if msg.id == ctx.message.id:
                    continue
                custom_emoji_match = re.search(r'<(a?):([a-zA-Z0-9_]+):([0-9]+)>', msg.content)
                if custom_emoji_match:
                    animated = bool(custom_emoji_match.group(1))
                    name = custom_emoji_match.group(2)
                    emoji_id = int(custom_emoji_match.group(3))
                    emoji = discord.PartialEmoji(animated=animated, name=name, id=emoji_id)
                    break

        if not emoji:
            await ctx.send("Sift wla replyi l emoji li bghitni nchfer.")
            return

        try:
            file_bytes = await emoji.read()

            created_emoji = await ctx.guild.create_custom_emoji(
                name=emoji.name,
                image=file_bytes
            )

            em = discord.Embed(
                title="Emoji Tzad!",
                description=f"**Name:** {created_emoji.name}\n**ID:** `{created_emoji.id}`\n**Emoji:** {created_emoji}",
                color=0x000000
            )
            em.set_thumbnail(url=created_emoji.url)
            await ctx.send(embed=em)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(
                embed=discord.Embed(description=f"Ma9dertch nchfer emoji **{emoji.name}** :/ `{e}`", color=0x000000))

    @emoji.command(name="zoom", aliases=["z"], help="Chouf tswira ta3 chy emoji.")
    async def emoji_zoom(self, ctx, emoji: discord.PartialEmoji = None):
        if not emoji and ctx.message.reference:
            try:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref_msg.content:
                    custom_emoji_match = re.search(r'<(a?):([a-zA-Z0-9_]+):([0-9]+)>', ref_msg.content)
                    if custom_emoji_match:
                        animated = bool(custom_emoji_match.group(1))
                        name = custom_emoji_match.group(2)
                        emoji_id = int(custom_emoji_match.group(3))
                        emoji = discord.PartialEmoji(animated=animated, name=name, id=emoji_id)
            except Exception:
                pass

        if not emoji and ctx.message.content:
            custom_emoji_match = re.search(r'<(a?):([a-zA-Z0-9_]+):([0-9]+)>', ctx.message.content)
            if custom_emoji_match:
                animated = bool(custom_emoji_match.group(1))
                name = custom_emoji_match.group(2)
                emoji_id = int(custom_emoji_match.group(3))
                emoji = discord.PartialEmoji(animated=animated, name=name, id=emoji_id)

        if not emoji:
            async for msg in ctx.channel.history(limit=20):
                if msg.id == ctx.message.id:
                    continue
                custom_emoji_match = re.search(r'<(a?):([a-zA-Z0-9_]+):([0-9]+)>', msg.content)
                if custom_emoji_match:
                    animated = bool(custom_emoji_match.group(1))
                    name = custom_emoji_match.group(2)
                    emoji_id = int(custom_emoji_match.group(3))
                    emoji = discord.PartialEmoji(animated=animated, name=name, id=emoji_id)
                    break

        if not emoji:
            await ctx.send("3tini emoji li bghitini nzoomi wla replyi l chy message fih emoji.")
            return

        try:
            em = discord.Embed(
                title=f"Zoom: :{emoji.name}:",
                description=f"**ID:** `{emoji.id}`",
                color=0x000000
            )
            em.set_image(url=emoji.url)
            await ctx.send(embed=em)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"Mal9itch had emoji :/ `{e}`", color=0x000000))

    @commands.command(pass_context=True, aliases=["nick", "nickname"], help="Bdel nickname ta3 chy wa7d.")
    @commands.has_permissions(manage_nicknames=True)
    async def setnick(self, ctx, member: FuzzyMember = None, *, nick=None):
        if member is None:
            await ctx.send("Lmen bghiti tbdel nickname?")
        else:
            await member.edit(nick=nick)
            await ctx.send(f"Bdelt nickname ta3 **{member}** l **{nick}**")

    @commands.command(aliases=["skt", "skot"], help="Muti chy wa7d.")
    @commands.has_permissions(manage_messages=True)
    async def mute(self, ctx, member: FuzzyMember):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch tmuti chy wa7d b7alk wla fo9 mnk f role ._.")
            return

        role = discord.utils.get(ctx.guild.roles, name='0')

        if not role:
            try:
                role = await ctx.guild.create_role(
                    name="0",
                    reason="Muted role dynamically created by the bot.",
                    color=discord.Color.dark_grey()
                )

                # Move role position as high as possible (below the bot's own highest role)
                max_pos = ctx.guild.me.top_role.position
                if max_pos > 1:
                    try:
                        await role.edit(position=max_pos - 1)
                    except Exception as e:
                        traceback.print_exc()

                # Get all moderator roles in the guild
                mod_roles = [
                    r for r in ctx.guild.roles
                    if not r.is_default() and (
                        r.permissions.manage_messages
                        or r.permissions.kick_members
                        or r.permissions.ban_members
                        or r.permissions.moderate_members
                        or r.permissions.administrator
                    )
                ]

                # Set permissions in all text/voice/stage channels
                for channel in ctx.guild.channels:
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)):
                        try:
                            # Deny sending/reacting for muted role
                            await channel.set_permissions(role, send_messages=False, add_reactions=False)
                            # Allow sending for moderator roles
                            for mod_role in mod_roles:
                                await channel.set_permissions(mod_role, send_messages=True)
                        except Exception:
                            pass
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"Ma9ditch ncreati role '0' :/ `{e}`",
                                                   color=0x000000))
                return

        try:
            await member.add_roles(role)
            await ctx.send(f"{member.mention} skt wa7d chwya.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Tra chy mochkil :/ `{e}`", color=0x000000))

    @commands.command(aliases=["hder", "hdr", "hdar"], help="Unmuti chy wa7d.")
    @commands.has_permissions(manage_messages=True)
    async def unmute(self, ctx, member: FuzzyMember):
        role = discord.utils.get(ctx.guild.roles, name='0')

        if not role or role not in member.roles:
            await ctx.send(f"**{member.display_name}** mamutich aslan.")
            return

        try:
            await member.remove_roles(role)
            embed = discord.Embed(description=f"{member.mention} sf hder db.", color=0x000000)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9ditch n7yed lih role :/ `{e}`", color=0x000000))

    

    @commands.command(name="timeout", aliases=["to", "ghber", "ghbr"], help="Dir timeout l chy wa7d.")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: FuzzyMember, duration: str = None):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch dir timeout lchy wa7d b7alk wla fo9 mnk f role ._.")
            return

        if not duration:
            await ctx.send(f"3tini duration ta3 timeout. (e.g., `10m`, `2h`, `1d`)")
            return

        delta = self.parse_duration(duration)
        if not delta:
            await ctx.send("Lw9t li drti makhdamch. Ktb format b7al: `15m`, `1h`, `3d`.")
            return

        try:
            await member.timeout(delta, reason="Timed out through Sifdine")
            await ctx.send(f"{member.mention} ayghber wa7d `{duration}`.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Tra mochkil :/ `{e}`", color=0x000000))

    @commands.command(name="untimeout", aliases=["rje3", "reje3"])
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: FuzzyMember):
        try:
            await member.timeout(None, reason="Untimed out though Sifdine.")
            await ctx.send(f"{member.mention} salat lih l3o9oba.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch n7yed timeout l **{member.display_name}**: `{e}`", color=0x000000))

    @commands.command(name="jail", aliases=["7bibis"], help="Seft chy wa7d l7bibis.")
    @commands.has_permissions(moderate_members=True)
    async def jail(self, ctx, member: FuzzyMember):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("Mat9edch tsift chy wa7d b7alk wla fo9 mnk f role l7ebs ._.")
            return

        # 1. Fetch channel & role references
        jail_channel = discord.utils.get(ctx.guild.text_channels, name="cll")
        jail_role = discord.utils.get(ctx.guild.roles, name="Jailed")
        role_was_created = False

        # 2. Create "Jailed" role if missing
        if not jail_role:
            try:
                jail_role = await ctx.guild.create_role(name="Jailed", color=discord.Color.from_rgb(20, 20, 20))
                role_was_created = True
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"Ma9dertch ncreer role 'Jailed' :/ `{e}`", color=0x000000))
                return

        # 3. Create "cll" channel if missing
        if not jail_channel:
            try:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    jail_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    )
                }
                jail_channel = await ctx.guild.create_text_channel(
                    name="cll",
                    overwrites=overwrites,
                    topic="L7bibis"
                )
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"Ma9dertch ncreati channel ta3 jail :/ `{e}`", color=0x000000))
                return

        # 4. If role was just created, apply permissions across ALL channels cleanly
        if role_was_created:
            for channel in ctx.guild.channels:
                try:
                    if channel.id == jail_channel.id:
                        await channel.set_permissions(
                        jail_role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    )
                    else:
                        await channel.set_permissions(jail_role, view_channel=False)
                except Exception:
                    pass

        # 5. Add Jailed role & disconnect from voice if currently connected
        try:
            await member.add_roles(jail_role)
        
            if member.voice and member.voice.channel:
                try:
                    await member.move_to(None)
                except Exception:
                    pass

            await ctx.send(f"{member.mention} mcha l7bibis.")
            await jail_channel.send(f"{member.mention} mr7ba bik fl7bibis.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Tra chy mochkil :/ `{e}`", color=0x000000))

    @commands.command(name="unjail", aliases=["free", "tl9", "tle9", "tla9"], help="Kherrej chy wa7d mn l7bibis.")
    @commands.has_permissions(moderate_members=True)
    async def unjail(self, ctx, member: FuzzyMember):
        jail_role = discord.utils.get(ctx.guild.roles, name="Jailed")

        if not jail_role or jail_role not in member.roles:
            await ctx.send(
                embed=discord.Embed(description=f"**{member.name}** makaynch fl7ebs aslan.", color=0x000000))
            return

        try:
            await member.remove_roles(jail_role)
            await ctx.send(f"{member.mention} khrej mn l7ebs.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Tra chy mochkil :/ `{e}`", color=0x000000))

    @commands.command(name="antibot", aliases=["ab"], help="Mse7 messagat ta3 chy bot w 7ebso.")
    @commands.has_permissions(moderate_members=True)
    async def antibot(self, ctx, member: FuzzyMember):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch tdir hada l chi b7alk wla fo9 mnk f role ._.")
            return

        deleted_count = 0
        for channel in ctx.guild.text_channels:
            try:
                def is_member(m):
                    return m.author == member
                await channel.purge(limit=5, check=is_member)
                deleted_count += 1
            except Exception:
                pass

        jail_role = discord.utils.get(ctx.guild.roles, name="Jailed")
        if not jail_role:
            try:
                jail_role = await ctx.guild.create_role(name="Jailed", color=discord.Color.from_rgb(20, 20, 20))
                for channel in ctx.guild.text_channels:
                    if channel.name != "cll":
                        try:
                            await channel.set_permissions(jail_role, view_channel=False)
                        except Exception:
                            pass
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"Ma9dertch ncreer role 'Jailed' :/ `{e}`", color=0x000000))
                return

        try:
            await member.add_roles(jail_role)
            await ctx.send(f"{member.mention} mcha l7bibis. (Mse7t 5 messages mn {deleted_count} channels)")
            jail_channel = discord.utils.get(ctx.guild.text_channels, name="cll")
            if jail_channel:
                await jail_channel.send(f"{member.mention} mr7ba bik fl7bibis.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Tra chy mochkil :/ `{e}`", color=0x000000))

    @commands.command(name="kick", aliases=["kicki"], help="Kick chy wa7d mn server.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: FuzzyMember, *, reason: str = None):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch tkick chy wa7d b7alk wla fo9 mnk f role ._.")
            return

        try:
            await member.kick(reason=reason)
            await ctx.send(f"{member.mention} tms7 mn server. Reason: {reason or 'Makaynch'}")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch nkick **{member.display_name}**: `{e}`", color=0x000000))

    @commands.command(name="ban", aliases=["banni"], help="Ban chy wa7d mn server.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: FuzzyMember, *, reason: str = None):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch tban chy wa7d b7alk wla fo9 mnk f role ._.")
            return

        try:
            await member.ban(reason=reason)
            await ctx.send(f"{member.mention} tbanna mn server. Reason: {reason or 'Makaynch'}")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch nban **{member.display_name}**: `{e}`", color=0x000000))

    @commands.command(name="unban", aliases=["unbanni"], help="Unban chy wa7d mn server.")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, user_id: int):
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user)
            await ctx.send(f"{user.mention} (ID: {user_id}) t unbanna.")
        except discord.NotFound:
            await ctx.send("Mal9itch user b had l ID.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch n7yed l ban: `{e}`", color=0x000000))

    @commands.command(name="banlist", aliases=["bl", "bans"], help="Chouf list ta3 bans ta3 server.")
    @commands.has_permissions(ban_members=True)
    async def banlist(self, ctx):
        if not ctx.guild:
            await ctx.send("Had lcommand khdama gher fservers.")
            return

        bans = []
        async for ban_entry in ctx.guild.bans():
            bans.append(f"• {ban_entry.user} (ID: {ban_entry.user.id}) — Reason: {ban_entry.reason or 'Makaynch'}")

        if not bans:
            await ctx.send("Server mafih 7ta chi ban.")
            return

        view = self.bot.Paginator(
            ctx,
            pages=bans,
            per_page=10,
            title=f"Ban list ta3 {ctx.guild.name}"
        )
        initial_embed = view.get_page()
        msg = await ctx.send(embed=initial_embed, view=view)
        view.message = msg

    @commands.command(name="voicemute", aliases=["vmute"], help="Muti chy wa7d f voice.")
    @commands.has_permissions(moderate_members=True)
    async def voicemute(self, ctx, member: FuzzyMember):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch tmuti chy wa7d b7alk wla fo9 mnk f role ._.")
            return

        if not member.voice:
            await ctx.send(f"{member.mention} makaynch f voice channel.")
            return

        try:
            await member.edit(mute=True)
            await ctx.send(f"{member.mention} tmuta fl voice channel.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch nmuti **{member.display_name}**: `{e}`", color=0x000000))

    @commands.command(name="voiceunmute", aliases=["vunmute"], help="Unmuti chy wa7d f voice.")
    @commands.has_permissions(moderate_members=True)
    async def voiceunmute(self, ctx, member: FuzzyMember):
        if not member.voice:
            await ctx.send(f"{member.mention} makaynch f voice channel.")
            return

        try:
            await member.edit(mute=False)
            await ctx.send(f"{member.mention} t unmuta fl voice channel.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch n7yed l mute: `{e}`", color=0x000000))

    @commands.command(name="deafen", help="Deafeni chy wa7d f voice.")
    @commands.has_permissions(moderate_members=True)
    async def deafen(self, ctx, member: FuzzyMember):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch tdeafen chy wa7d b7alk wla fo9 mnk f role ._.")
            return

        if not member.voice:
            await ctx.send(f"{member.mention} makaynch f voice channel.")
            return

        try:
            await member.edit(deafen=True)
            await ctx.send(f"{member.mention} tdeafena f voice channel.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch ndeafen **{member.display_name}**: `{e}`", color=0x000000))

    @commands.command(name="undeafen", help="Undeafeni chy wa7d f voice.")
    @commands.has_permissions(moderate_members=True)
    async def undeafen(self, ctx, member: FuzzyMember):
        if not member.voice:
            await ctx.send(f"{member.mention} makaynch f voice channel.")
            return

        try:
            await member.edit(deafen=False)
            await ctx.send(f"{member.mention} t undeafena fl voice channel.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch n7yed l deafen: `{e}`", color=0x000000))
    

    @commands.command(name="disconnect", aliases=["dc", "kickvc"], help="Disconnect chy wa7d mn voice.")
    @commands.has_permissions(moderate_members=True)
    async def disconnect(self, ctx, member: FuzzyMember):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send(f"Mat9edch tkick chy wa7d b7alk wla fo9 mnk f role ._.")
            return

        if not member.voice:
            await ctx.send(f"{member.mention} makaynch f voice channel.")
            return

        try:
            await member.move_to(None)
            await ctx.send(f"{member.mention} tdisconnecta mn voice channel.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch ndisconnect **{member.display_name}**: `{e}`", color=0x000000))

    @commands.command(name="voicenuke", aliases=["nuke"], help="Disconnect kolchi mn chy voice channel.")
    @commands.has_permissions(manage_channels=True)
    async def voicenuke(self, ctx, channel: discord.VoiceChannel = None):
        if not channel:
            if not ctx.author.voice:
                await ctx.send("Khsek tkon f voice channel wla t3tini channel.")
                return
            channel = ctx.author.voice.channel

        if not channel.members:
            await ctx.send(f"Channel {channel.mention} khawi.")
            return

        count = 0
        for member in channel.members:
            try:
                await member.move_to(None)
                count += 1
            except Exception:
                pass

        await ctx.send(f"Disconnectit {count} wa7d mn {channel.mention}.")

    @commands.command(name="slowmode", aliases=["slow"], help="Zid wla 7yed slowmode f channel.")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = 0):
        if seconds < 0 or seconds > 21600:
            await ctx.send("Slowmode khso ykon bin 0 w 21600 seconds (6 hours).")
            return

        try:
            await ctx.channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await ctx.send("Slowmode t7yed.")
            else:
                await ctx.send(f"Slowmode tzad: {seconds} seconds.")
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Ma9dertch nbdel slowmode: `{e}`", color=0x000000))

    @commands.command(name="permissions", aliases=["perms", "perm"], help="Chouf permissions ta3 chy wa7d.")
    @commands.has_permissions(moderate_members=True)
    async def permissions(self, ctx, member: FuzzyMember = None):
        if not ctx.guild:
            await ctx.send("Had lcommand khdama gher fservers.")
            return

        member = member or ctx.author
        perms = member.guild_permissions

        enabled_perms = [perm.replace('_', ' ').title() for perm, value in perms if value]
        disabled_perms = [perm.replace('_', ' ').title() for perm, value in perms if not value]

        embed = discord.Embed(title=f"Permissions ta3 {member.display_name}", color=0x000000)
        
        if enabled_perms:
            embed.add_field(name="✅ Enabled", value="\n".join(f"• {p}" for p in enabled_perms[:25]), inline=True)
        if disabled_perms:
            embed.add_field(name="❌ Disabled", value="\n".join(f"• {p}" for p in disabled_perms[:25]), inline=True)
        
        embed.set_footer(text=f"Total: {len(enabled_perms)} enabled, {len(disabled_perms)} disabled")
        await ctx.send(embed=embed)

    @commands.command(name="logs", aliases=["log", "logging", "audit"], help="Configuri log channel (dir nafs channel bach t7bs logs).")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def logs(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        async with self.bot.db.execute("SELECT channel_id FROM guild_logs WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()

        current_channel_id = row[0] if row else None

        if channel is None:
            if current_channel_id:
                cur_chan = ctx.guild.get_channel(current_channel_id)
                chan_str = cur_chan.mention if cur_chan else f"`#{current_channel_id}`"
                await ctx.send(embed=discord.Embed(
                    description=f"📋 **Log Channel:** {chan_str}\n\nBach tbdel channel: `{ctx.prefix}logs <#channel>`\n-# _Dir nafs channel bach t7bs logs._",
                    color=0x000000
                ))
            else:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ Ta log channel ma mconfiguri f had server.\n\nDir `{ctx.prefix}logs <#channel>` bach tbda logging.",
                    color=0x000000
                ))
            return

        # Case 1: Same channel provided -> Disable/remove logging
        if current_channel_id == channel.id:
            async with self.bot.db.execute("DELETE FROM guild_logs WHERE guild_id = ?", (ctx.guild.id,)):
                await self.bot.db.commit()

            events_cog = self.bot.get_cog("Events")
            if events_cog and hasattr(events_cog, "log_channels"):
                events_cog.log_channels.pop(ctx.guild.id, None)

            await ctx.send(embed=discord.Embed(
                description=f"🛑 **Logging 7bes** f {channel.mention}.",
                color=0x000000
            ))
            return

        # Case 2: New channel provided (or switching channel)
        bot_perms = channel.permissions_for(ctx.guild.me)
        if not (bot_perms.send_messages and bot_perms.embed_links):
            await ctx.send(embed=discord.Embed(
                description=f"❌ Ma3ndich permissions dial `Send Messages` o `Embed Links` f {channel.mention}.",
                color=0x000000
            ))
            return

        async with self.bot.db.execute("""
            INSERT INTO guild_logs (guild_id, channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
        """, (ctx.guild.id, channel.id)):
            await self.bot.db.commit()

        events_cog = self.bot.get_cog("Events")
        if events_cog and hasattr(events_cog, "log_channels"):
            events_cog.log_channels[ctx.guild.id] = channel.id

        await ctx.send(embed=discord.Embed(
            description=f"✅ **Log Channel tconfigura:** {channel.mention}\nLogging rah bda daba.",
            color=0x000000
        ))


async def setup(bot):
    await bot.add_cog(Moderation(bot))