import discord
from discord.ext import commands


class JoinToCreate(commands.Cog):
    """
    Join-to-Create voice channels.

    Flow:
      - Admin runs `vc setup` once to create the hub channel + category.
      - Any member joining the hub gets their own temp VC and is moved into it.
      - The owner gets a set of self-service commands limited to THEIR channel only.
        None of these commands touch server moderation (no server kick/ban, no role
        edits, no permission changes outside that one voice channel).
      - The channel is deleted automatically once everyone leaves it.
    """

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.db.execute(
            "CREATE TABLE IF NOT EXISTS jtc_hubs ("
            "guild_id INTEGER PRIMARY KEY, "
            "hub_channel_id INTEGER, "
            "category_id INTEGER)"
        )
        await self.bot.db.execute(
            "CREATE TABLE IF NOT EXISTS jtc_channels ("
            "channel_id INTEGER PRIMARY KEY, "
            "guild_id INTEGER, "
            "owner_id INTEGER)"
        )
        await self.bot.db.commit()

    # ---------- helpers ----------

    async def get_hub(self, guild_id: int):
        async with self.bot.db.execute(
            "SELECT hub_channel_id, category_id FROM jtc_hubs WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def get_owned_channel(self, guild_id: int, user_id: int):
        """Returns the channel_id of the temp VC this user currently owns, or None."""
        async with self.bot.db.execute(
            "SELECT channel_id FROM jtc_channels WHERE guild_id = ? AND owner_id = ?",
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_owner(self, channel_id: int):
        async with self.bot.db.execute(
            "SELECT owner_id FROM jtc_channels WHERE channel_id = ?", (channel_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_owner(self, channel_id: int, owner_id: int):
        await self.bot.db.execute(
            "UPDATE jtc_channels SET owner_id = ? WHERE channel_id = ?", (owner_id, channel_id)
        )
        await self.bot.db.commit()

    async def is_temp_channel(self, channel_id: int) -> bool:
        async with self.bot.db.execute(
            "SELECT 1 FROM jtc_channels WHERE channel_id = ?", (channel_id,)
        ) as cursor:
            return (await cursor.fetchone()) is not None

    async def require_owner_channel(self, ctx: commands.Context):
        """
        Returns the member's voice channel if:
          - they are in voice
          - that voice channel is a temp JTC channel
          - they are the recorded owner of it
        Otherwise sends an explanatory message and returns None.
        This is what keeps these commands scoped to "your own channel only".
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("Khassk tkoun f voice channel dyalk bach dir hadchi.")
            return None

        channel = ctx.author.voice.channel
        if not await self.is_temp_channel(channel.id):
            await ctx.reply("Hada machi channel li tsawb b Join-to-Create.")
            return None

        owner_id = await self.get_owner(channel.id)
        if owner_id != ctx.author.id:
            await ctx.reply("Ghi owner dyal had channel li ymken ydir hadchi.")
            return None

        return channel

    # ---------- setup (admin) ----------

    @commands.command(name="jtcsetup", aliases=["vcsetup"])
    @commands.has_permissions(manage_channels=True, manage_roles=True)
    @commands.bot_has_permissions(manage_channels=True, manage_roles=True, move_members=True)
    async def jtcsetup(self, ctx: commands.Context, *, hub_name: str = "➕ Join to Create"):
        """One-time setup: creates the hub voice channel + category for temp channels."""
        category = await ctx.guild.create_category("Voice Channels", reason="Join-to-Create setup")
        hub = await ctx.guild.create_voice_channel(hub_name, category=category, reason="Join-to-Create setup")

        await self.bot.db.execute(
            "INSERT INTO jtc_hubs (guild_id, hub_channel_id, category_id) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET hub_channel_id = excluded.hub_channel_id, "
            "category_id = excluded.category_id",
            (ctx.guild.id, hub.id, category.id),
        )
        await self.bot.db.commit()

        await ctx.reply(
            f"Sawbt l hub: **{hub.name}**. Kol chi li ydkhol lih ghadi ykhalq lo channel dyalo."
        )

    # ---------- tutorial embed ----------

    async def resolve_display_prefix(self, guild: discord.Guild) -> str:
        """Best-effort guess at the prefix to show in the tutorial (mirrors main.py's get_prefix)."""
        async with self.bot.db.execute(
            "SELECT prefix FROM guild_prefixes WHERE guild_id = ?", (guild.id,)
        ) as cursor:
            row = await cursor.fetchone()
        return f"{row[0]} " if row else "sat "

    def build_tutorial_embed(self, member: discord.Member, prefix: str) -> discord.Embed:
        embed = discord.Embed(
            title="🎙️ This is your channel",
            description=f"{member.mention}, you own this voice channel. Here's what you can do with it:",
            color=0x000000,
        )
        embed.add_field(name=f"{prefix}vclock", value="Lock the channel so no one new can join", inline=False)
        embed.add_field(name=f"{prefix}vcunlock", value="Unlock the channel", inline=False)
        embed.add_field(name=f"{prefix}vclimit <n>", value="Set a max number of members (0 = unlimited)", inline=False)
        embed.add_field(name=f"{prefix}vcname <name>", value="Rename the channel", inline=False)
        embed.add_field(name=f"{prefix}vcpermit <member>", value="Let someone in even while locked", inline=False)
        embed.add_field(name=f"{prefix}vcreject <member>", value="Block someone and disconnect them", inline=False)
        embed.add_field(name=f"{prefix}vckick <member>", value="Disconnect someone from this channel only", inline=False)
        embed.add_field(name=f"{prefix}vcclaim", value="Claim ownership if the owner has left", inline=False)
        embed.set_footer(text="These commands only ever work in your own channel.")
        return embed

    # ---------- voice state handling ----------

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild
        hub_row = await self.get_hub(guild.id)

        # Joined the hub -> create a personal channel and move them in
        if after.channel and hub_row and after.channel.id == hub_row[0]:
            hub_channel = after.channel  # the actual hub the member just joined
            category = hub_channel.category  # always mirrors reality, even if it was moved/recreated
            if category is None:
                category = await guild.create_category("Voice Channels", reason="Join-to-Create: hub had no category")
                try:
                    await hub_channel.move(category=category, reason="Join-to-Create: re-parenting hub")
                except discord.HTTPException:
                    pass
            try:
                new_channel = await guild.create_voice_channel(
                    name=f"{member.display_name}'s channel",
                    category=category,
                    reason="Join-to-Create",
                )
                await new_channel.set_permissions(
                    member,
                    connect=True,
                    manage_channels=False,  # owner controls go through bot commands, not raw Discord perms
                    reason="Join-to-Create owner",
                )
                await member.move_to(new_channel, reason="Join-to-Create")

                await self.bot.db.execute(
                    "INSERT INTO jtc_channels (channel_id, guild_id, owner_id) VALUES (?, ?, ?)",
                    (new_channel.id, guild.id, member.id),
                )
                await self.bot.db.commit()

                prefix = await self.resolve_display_prefix(guild)
                try:
                    await new_channel.send(embed=self.build_tutorial_embed(member, prefix))
                except discord.Forbidden:
                    pass  # bot can't send text in this voice channel; skip silently
            except discord.Forbidden:
                pass  # missing permissions; nothing more we can do silently

        # Left a temp channel -> delete it if now empty, or hand off ownership
        if before.channel and await self.is_temp_channel(before.channel.id):
            channel = before.channel
            if len(channel.members) == 0:
                await self.bot.db.execute("DELETE FROM jtc_channels WHERE channel_id = ?", (channel.id,))
                await self.bot.db.commit()
                try:
                    await channel.delete(reason="Join-to-Create: empty")
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    pass

    # ---------- owner self-service commands ----------
    # Every command below is gated by require_owner_channel(), so it only ever
    # touches the caller's own temp voice channel — never server moderation.

    @commands.command(name="vclock")
    async def vclock(self, ctx: commands.Context):
        """Locks your channel so no one new can join."""
        channel = await self.require_owner_channel(ctx)
        if not channel:
            return
        await channel.set_permissions(ctx.guild.default_role, connect=False)
        await ctx.reply("🔒 Channel dyalk tsd.")

    @commands.command(name="vcunlock")
    async def vcunlock(self, ctx: commands.Context):
        """Unlocks your channel so anyone can join again."""
        channel = await self.require_owner_channel(ctx)
        if not channel:
            return
        await channel.set_permissions(ctx.guild.default_role, connect=None)
        await ctx.reply("🔓 Channel dyalk t7ell.")

    @commands.command(name="vclimit")
    async def vclimit(self, ctx: commands.Context, limit: int):
        """Sets a user limit for your channel (0 = unlimited)."""
        channel = await self.require_owner_channel(ctx)
        if not channel:
            return
        limit = max(0, min(limit, 99))
        await channel.edit(user_limit=limit)
        await ctx.reply(f"Limit dyal channel wela {limit if limit else 'unlimited'}.")

    @commands.command(name="vcname")
    async def vcname(self, ctx: commands.Context, *, new_name: str):
        """Renames your channel."""
        channel = await self.require_owner_channel(ctx)
        if not channel:
            return
        new_name = new_name[:100]
        await channel.edit(name=new_name)
        await ctx.reply(f"Smya Jdida : **{new_name}**.")

    @commands.command(name="vcpermit", aliases=["vcallow"])
    async def vcpermit(self, ctx: commands.Context, member: discord.Member):
        """Lets a specific member join your locked channel."""
        channel = await self.require_owner_channel(ctx)
        if not channel:
            return
        await channel.set_permissions(member, connect=True)
        await ctx.reply(f"{member.mention} ymken ydkhol l channel dyalk daba.")

    @commands.command(name="vcreject", aliases=["vcdeny"])
    async def vcreject(self, ctx: commands.Context, member: discord.Member):
        """Blocks a specific member from your channel, and disconnects them if inside."""
        channel = await self.require_owner_channel(ctx)
        if not channel:
            return
        await channel.set_permissions(member, connect=False)
        if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
            try:
                await member.move_to(None, reason="Removed by JTC channel owner")
            except discord.Forbidden:
                pass
        await ctx.reply(f"{member.mention} may9derch ydkhol l channel dyalk.")

    @commands.command(name="vckick", aliases=["vcdisconnect"])
    async def vckick(self, ctx: commands.Context, member: discord.Member):
        """Disconnects a member from your channel only (not the server)."""
        channel = await self.require_owner_channel(ctx)
        if not channel:
            return
        if member.id == ctx.author.id:
            await ctx.reply("Ma ymkench tkiki rassk :)")
            return
        if not member.voice or not member.voice.channel or member.voice.channel.id != channel.id:
            await ctx.reply("Had l membre machi f channel dyalk.")
            return
        try:
            await member.move_to(None, reason="Removed by JTC channel owner")
        except discord.Forbidden:
            await ctx.reply("Mat9dertch tkiki had khona (permissions).")
            return
        await ctx.reply(f"{member.mention} tkika mn channel dyalk.")

    @commands.command(name="vcclaim")
    async def vcclaim(self, ctx: commands.Context):
        """Claim ownership of a JTC channel if the original owner has left it."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("Khassk tkoun f voice channel bach tclaimeha.")
            return

        channel = ctx.author.voice.channel
        if not await self.is_temp_channel(channel.id):
            await ctx.reply("Hada machi channel dyal Join-to-Create.")
            return

        owner_id = await self.get_owner(channel.id)
        owner_still_here = owner_id is not None and any(m.id == owner_id for m in channel.members)

        if owner_still_here:
            await ctx.reply("L owner mazal f channel, ma ymkenlekch tclaimeha.")
            return

        await self.set_owner(channel.id, ctx.author.id)
        await channel.set_permissions(ctx.author, connect=True)
        await ctx.reply(f"{ctx.author.mention} howa l owner jdid dyal had channel.")


async def setup(bot):
    await bot.add_cog(JoinToCreate(bot))