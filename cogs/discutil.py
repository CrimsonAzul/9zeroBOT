from discord import asset
import discord
from discord.ext import commands

from converters import FuzzyMember

class DiscordUtil(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def get_clean_asset_url(asset: discord.Asset) -> str:
        if not asset:
            return ""
        if asset.is_animated():
            return asset.with_format("gif").with_size(1024).url
        return asset.with_format("png").with_size(1024).url

    @commands.command(name="serverinfo", aliases=["server", "guild", "guildinfo"], help="Informations 3la server.")
    @commands.guild_only()
    async def serverinfo(self, ctx):
        guild = ctx.guild


        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)


        roles_count = len(guild.roles)
        emojis_count = len(guild.emojis)
        stickers_count = len(guild.stickers)

        embed = discord.Embed(title=guild.name, color=0x000000, timestamp=ctx.message.created_at)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.add_field(name="Identity",
                        value=f"• **ID:** `{guild.id}`\n• **Owner:** {guild.owner} (`{guild.owner_id}`)", inline=False)
        embed.add_field(name="Metrics",
                        value=f"• **Members:** `{guild.member_count}`\n• **Boosts:** `{guild.premium_subscription_count}` (Level `{guild.premium_tier}`)",
                        inline=True)
        embed.add_field(name="Channels",
                        value=f"• **Categories:** `{categories}`\n• **Text:** `{text_channels}`\n• **Voice:** `{voice_channels}`",
                        inline=True)
        embed.add_field(name="Assets",
                        value=f"• **Roles:** `{roles_count}`\n• **Emojis:** `{emojis_count}`\n• **Stickers:** `{stickers_count}`",
                        inline=False)
        embed.add_field(name="Created On", value=discord.utils.format_dt(guild.created_at,
                                                                         style="F") + f" ({discord.utils.format_dt(guild.created_at, style='R')})",
                        inline=False)

        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


    @commands.command(name="servericon", aliases=["icon"], help="Tswira ta3 server.")
    @commands.guild_only()
    async def servericon(self, ctx):
        guild = ctx.guild
        if not guild.icon:
            await ctx.send("Had server ma3ndouch icon ._.")
            return

        embed = discord.Embed(title=f"Icon ta3 {guild.name}", color=0x000000)
        embed.set_image(url=guild.icon.url)
        await ctx.send(embed=embed)


    @commands.command(name="userinfo", aliases=["ui", "user", "whois"], help=f"Informations 3la chy wa7d.")
    @commands.guild_only()
    async def userinfo(self, ctx, member: FuzzyMember = None):
        member = member or ctx.author


        roles = [role.mention for role in member.roles[1:]]
        roles.reverse()
        roles_display = ", ".join(roles) if roles else "None"


        permissions = [perm[0].replace('_', ' ').title() for perm in member.guild_permissions if perm[1]]
        is_key_admin = "Administrator" in permissions or member.id == ctx.guild.owner_id

        embed = discord.Embed(title=f"Chkoun {member}?", color=0x000000, timestamp=ctx.message.created_at)
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="Identity", value=f"• **ID:** `{member.id}`\n• **Bot:** `{'Yes' if member.bot else 'No'}`",
                        inline=False)
        embed.add_field(name="Dates",
                        value=f"• **Joined Discord:** {discord.utils.format_dt(member.created_at, style='R')}\n• **Joined Server:** {discord.utils.format_dt(member.joined_at, style='R') if member.joined_at else 'Unknown'}",
                        inline=False)
        embed.add_field(name=f"Roles [{len(roles)}]", value=roles_display, inline=False)

        if is_key_admin:
            embed.add_field(name="Key Acknowledgements", value="`Server Authority / Administrator`", inline=False)

        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


    @commands.command(name="avatar", aliases=["av"], help="Tswira ta3k wla ta3 chy wa7d.")
    async def avatar(self, ctx, user: FuzzyMember = None):
        user = user or ctx.author
        asset = user.display_avatar
        avatar_url = self.get_clean_asset_url(asset)

        embed = discord.Embed(title=f"Avatar ta3 {user.display_name}", color=0x000000)

        # Download Links Fallback
        gif_str = f"[GIF]({asset.with_format('gif').with_size(1024).url}) | " if asset.is_animated() else ""
        png_str = f"[PNG]({asset.with_format('png').with_size(1024).url})"
        webp_str = f" | [WEBP]({asset.with_format('webp').with_size(1024).url})"
        embed.description = f"🔗 **Direct Links:** {gif_str}{png_str}{webp_str}"

        embed.set_image(url=avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="banner", help="Banner ta3k wla ta3 chy wa7d")
    async def banner(self, ctx, user: FuzzyMember = None):
        user = user or ctx.author

        # Force fetch to ensure banner data is populated
        fetched_user = await self.bot.fetch_user(user.id)
        embed = discord.Embed(title=f"Banner ta3 {user.display_name}", color=0x000000)

        if fetched_user.banner:
            asset = fetched_user.banner
            banner_url = self.get_clean_asset_url(asset)

            gif_str = f"[GIF]({asset.with_format('gif').with_size(1024).url}) | " if asset.is_animated() else ""
            png_str = f"[PNG]({asset.with_format('png').with_size(1024).url})"
            embed.description = f"🔗 **Direct Links:** {gif_str}{png_str}"
            embed.set_image(url=banner_url)

        elif fetched_user.accent_color:
            hex_color = str(fetched_user.accent_color).lstrip('#')
            fallback_banner_url = f"https://dummyimage.com/600x240/{hex_color}/{hex_color}.png"
            embed.set_image(url=fallback_banner_url)
            embed.set_footer(text="Using profile accent color fallback banner")
        else:
            await ctx.send(f"**{user.display_name}** ma3ndouch banner wla accent color.")
            return

        await ctx.send(embed=embed)

    @commands.command(name="serveravatar", aliases=["sav", "guildavatar"], help="Tswira li dayr khouna f had server.")
    @commands.guild_only()
    async def serveravatar(self, ctx, member: FuzzyMember = None):
        member = member or ctx.author

        if not member.guild_avatar:
            await ctx.send(f"**{member.display_name}** ma3ndouch local avatar f had server.")
            return

        asset = member.guild_avatar
        server_avatar_url = self.get_clean_asset_url(asset)

        embed = discord.Embed(title=f"Server avatar ta3 {member.display_name}", color=0x000000)

        gif_str = f"[GIF]({asset.with_format('gif').with_size(1024).url}) | " if asset.is_animated() else ""
        png_str = f"[PNG]({asset.with_format('png').with_size(1024).url})"
        embed.description = f"🔗 **Direct Links:** {gif_str}{png_str}"

        embed.set_image(url=server_avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="boosts", aliases=["boost", "booster", "boosters"], help="Server ch7al fih mn boost o chkoun mboustih.")
    @commands.guild_only()
    async def boosts(self, ctx):
        guild = ctx.guild

        booster_role = guild.premium_subscriber_role
        rolemention = booster_role.mention if booster_role else "None"

        if guild.premium_subscription_count > 0:
            cached_boosters = [m for m in guild.members if m.premium_since]
            if not cached_boosters:
                try:
                    await guild.chunk(cache=True)
                except Exception:
                    pass

        booster_lines = []
        for member in guild.members:
            if member.premium_since:
                boost_count = 0
                for role in member.roles:
                    if role.is_premium_subscriber():
                        boost_count += 1

                boost_count = max(1, boost_count)
                booster_lines.append(
                    f"• {member.mention} - `{boost_count} boosts` (Since: {discord.utils.format_dt(member.premium_since, style='R')})")

        embed = discord.Embed(
            title=f"Boost Status - {guild.name}",
            color=0x000000,
            timestamp=ctx.message.created_at
        )

        embed.add_field(name="Overview",
                        value=f"• **Total Boosts:** `{guild.premium_subscription_count}`\n• **Level:** `{guild.premium_tier}`\n• **Booster Role:** {rolemention}",
                        inline=False)

        if booster_lines:
            embed.add_field(name=f"Active Boosters [{len(booster_lines)}]", value="\n".join(booster_lines),
                            inline=False)
        else:
            embed.add_field(name="Active Boosters [0]", value="Had server ma fih 7ta boost.", inline=False)

        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['gol', "goul", "9ol", "9oul"], help="Ana ngoul li bghiti.")
    async def say(self, ctx, *, saymsg=None):
        if saymsg == None:
            return await ctx.send('chno ngol ???')
        await ctx.send(saymsg)
        await ctx.message.delete()

    @commands.command(name="webhook", aliases=['disguise', 'wh'], help="Goul chy hdra bsmyit chy wa7d akhor.")
    @commands.guild_only()
    async def webhook(self, ctx, user: FuzzyMember, *, message: str):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        webhooks = await ctx.channel.webhooks()
        web = discord.utils.get(webhooks, name="SIFDINEWHCOMMAND")

        if not web:
            web = await ctx.channel.create_webhook(name="SIFDINEWHCOMMAND")

        await web.send(
            content=message,
            avatar_url=user.display_avatar.url,
            username=user.display_name
        )

    @commands.command(aliases=["dm", "prv"], help="Sift message anonyme l chy wa7d mn server.")
    async def whisper(self, ctx, user: FuzzyMember = None, *, msg):
        await ctx.message.delete()
        await user.send(f"**Anonymous user:** {msg}")


    @commands.command(help="Kteb b emojis blast text.")
    async def emojify(self, ctx, *, text):
        emojis = []
        for beans in text:
            if beans.isdecimal():
                num2word = {
                    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six",
                    "7": "seven",
                    "8": "eight", "9": "nine"
                }
                emojis.append(f':{num2word.get(beans)}:')
            elif beans.isalpha():
                emojis.append(f':regional_indicator_{beans}:')
            else:
                emojis.append(beans)
        await ctx.send(''.join(emojis))


    @commands.command(name="afk", aliases=["brb", "mamsalich", "mamsalish", "mamsalix"], help="Li pingak i3rfek mamsalich.")
    async def afk(self, ctx, *, reason: str = "AFK"):
        if len(reason) > 100:
            await ctx.send("Yak awdi labas.")
            return

        reason = discord.utils.remove_markdown(reason)

        async with self.bot.db.execute(
            "INSERT OR REPLACE INTO afk (user_id, reason, timestamp) VALUES (?, ?, ?)",
            (ctx.author.id, reason, int(ctx.message.created_at.timestamp()))
        ):
            await self.bot.db.commit()

        await ctx.send(f"Safi li swl fik angoulih rah **{reason}**.")

    @commands.command(name="snipe", aliases=["s"], help="Tchouf lmessagat li tmse7o.")
    async def snipe(self, ctx):
        cache = getattr(self.bot, "snipe_cache", {})
        channel_id = ctx.channel.id

        if channel_id not in cache or not cache[channel_id]:
            await ctx.send(embed=discord.Embed(description="Ta message matmse7 ._.", color=0x000000))
            return

        embeds = []
        for data in reversed(cache[channel_id]):
            em = discord.Embed(
                description=data["content"] or "_Empty_",
                color=0x000000,
                timestamp=data["time"]
            )
            em.set_author(name=data["author_name"], icon_url=data["author_avatar"])
            if data["attachment"]:
                em.set_image(url=data["attachment"])
            embeds.append(em)

        view = self.bot.Paginator(ctx, pages=embeds)
        initial_embed = view.get_page()
        msg = await ctx.send(embed=initial_embed, view=view)
        view.message = msg

    @commands.command(name="editsnipe", aliases=["esnipe", "es"], help="Tchouf lmessagat li t editaw.")
    async def editsnipe(self, ctx):
        cache = getattr(self.bot, "edit_cache", {})
        channel_id = ctx.channel.id

        if channel_id not in cache or not cache[channel_id]:
            await ctx.send(embed=discord.Embed(description="Ta message ma t edita ._.", color=0x000000))
            return

        embeds = []
        for data in reversed(cache[channel_id]):
            em = discord.Embed(
                color=0x000000,
                timestamp=data["time"]
            )
            em.set_author(name=data["author_name"], icon_url=data["author_avatar"])
            em.add_field(name="Before", value=data["old_content"] or "Empty", inline=False)
            em.add_field(name="After", value=data["new_content"] or "Empty", inline=False)
            embeds.append(em)

        view = self.bot.Paginator(ctx, pages=embeds)
        initial_embed = view.get_page()
        msg = await ctx.send(embed=initial_embed, view=view)
        view.message = msg

    @commands.command(name="reactionsnipe", aliases=["rsnipe", "rs"], help="Chouf reactions li t7ydo.")
    async def reactionsnipe(self, ctx):
        cache = getattr(self.bot, "reaction_cache", {})
        channel_id = ctx.channel.id

        if channel_id not in cache or not cache[channel_id]:
            await ctx.send(embed=discord.Embed(description="Ta reaction ma t7ydat ._.", color=0x000000))
            return

        embeds = []
        for data in reversed(cache[channel_id]):

            jump_url = f"https://discord.com/channels/{data['guild_id']}/{channel_id}/{data['message_id']}"

            em = discord.Embed(
                description=f"Removed **{data['emoji']}** from [this message]({jump_url})",
                color=0x000000,
                timestamp=data["time"]
            )
            em.set_author(name=data["author_name"], icon_url=data["author_avatar"])
            embeds.append(em)

        view = self.bot.Paginator(ctx, pages=embeds)
        initial_embed = view.get_page()
        msg = await ctx.send(embed=initial_embed, view=view)
        view.message = msg



async def setup(bot):
    await bot.add_cog(DiscordUtil(bot))