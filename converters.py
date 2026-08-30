import difflib
import discord
from discord.ext import commands


class FuzzyMember(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> discord.Member:
        # 1. Exact resolution (IDs, @mentions, exact usernames/nicknames)
        try:
            return await commands.MemberConverter().convert(ctx, argument)
        except commands.MemberNotFound:
            pass

        if not ctx.guild:
            raise commands.MemberNotFound(argument)

        arg_clean = argument.lower()
        matches = []

        # 2. Compare input against server members (dynamically query gateway or fallback to cache)
        try:
            members = await ctx.guild.query_members(query=argument, limit=50)
        except Exception:
            members = ctx.guild.members

        for member in members:
            names = {
                member.name.lower(),
                member.display_name.lower(),
            }
            if member.global_name:
                names.add(member.global_name.lower())
            if member.nick:
                names.add(member.nick.lower())

            highest_score_for_member = max(
                difflib.SequenceMatcher(None, arg_clean, name).ratio()
                for name in names
            )

            if highest_score_for_member >= 0.50:
                matches.append((highest_score_for_member, member))

        # 3. Select maximum similarity score
        if matches:
            best_match = max(matches, key=lambda x: x[0])[1]
            return best_match

        raise commands.MemberNotFound(argument)