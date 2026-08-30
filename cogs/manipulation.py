import urllib.parse
from typing import Optional
import discord
from discord.ext import commands
from converters import FuzzyMember

class Manipulation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def resolve_image(self, ctx, target: Optional[str] = None) -> str:
        if not target:
            if ctx.message.attachments:
                return ctx.message.attachments[0].url
            return ctx.author.display_avatar.url
        
        target_lower = target.lower()
        if target_lower.startswith("http://") or target_lower.startswith("https://"):
            return target
            
        try:
            member = await FuzzyMember().convert(ctx, target)
            return member.display_avatar.url
        except commands.CommandError:
            raise commands.BadArgument("Malkitch had l member, t79e9 men l smiya wla dir link direct.")


    @commands.command(name="worthless", help="Ma hdra ma walo.")
    async def worthless(self, ctx, *, text: str):
        quoted = urllib.parse.quote(text, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/worthless?text={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="drake", help="Meme ta3 drake.")
    async def drake(self, ctx, *, text: str):
        if "," in text:
            top, bottom = text.split(",", 1)
            top = top.strip()
            bottom = bottom.strip()
        else:
            top = text.strip()
            bottom = " "

        quoted1 = urllib.parse.quote(top, safe='')
        quoted2 = urllib.parse.quote(bottom, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/drake?text1={quoted1}&text2={quoted2}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="presidentialalert", aliases=["presidential", "alert", "notification", "noti"], help="Red lmessage ta3k notification.")
    async def presidentialalert(self, ctx, *, text: str):
        quoted = urllib.parse.quote(text, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/presidentialalert?text={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="spongebobburnpaper", help="Spongebob kay7re9 lmessage ta3k.")
    async def spongebobburnpaper(self, ctx, *, text: str):
        quoted = urllib.parse.quote(text, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/spongebobburnpaper?text={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="lisastage", aliases=["stage", "lisa"], help="Lisa katwri lmessage ta3k f stage.")
    async def lisastage(self, ctx, *, text: str):
        quoted = urllib.parse.quote(text, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/lisastage?text={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="changemymind", aliases=["changemind"], help="Change my mind okda.")
    async def changemymind(self, ctx, *, text: str):
        quoted = urllib.parse.quote(text, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/changemymind?text={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="awkwardmonkey", aliases=["sideeye"], help="Awkward monkey kaychouf fl message ta3k.")
    async def awkwardmonkey(self, ctx, *, text: str):
        quoted = urllib.parse.quote(text, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/awkwardmonkey?text={quoted}"
        await ctx.reply(url, mention_author=False)


    @commands.command(name="blur", aliases=["blurri"], help="Katred tswira mdbeba.")
    async def blur(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/blur?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="circle", aliases=["round", "dwer", "dower"], help="Katred tswira mdwra.")
    async def circle(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/circle?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="invert", help="Katinverti l alwan ta3 tswira.")
    async def invert(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/invert?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="wide", aliases=["stretch", "3erred"], help="Katred tswira 3rida.")
    async def wide(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/wide?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="uglyupclose", aliases=["ugly", "khayb"], help="Spongebob o basit kaygoulo lik ugly hh.")
    async def uglyupclose(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/uglyupclose?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="clown", aliases=["bahlawan"], help="Robin kaygoul lik nta bahlawan.")
    async def clown(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/clown?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="restinpeace", aliases=["rip", "layr7mo", "tr7mo3lih"], help="Tr7mo 3lih.")
    async def restinpeace(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/rip?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="affectbaby", aliases=["baby"], help="Lwalida drbat walakin ma9ysatch.")
    async def affectbaby(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/affectbaby?image={quoted}"
        await ctx.reply(url, mention_author=False)

    @commands.command(name="trash", aliases=["zbel", "throw", "lo7", "zbl", "rmi"], help="Katlo7 tswira fzbel.")
    async def trash(self, ctx, *, target: Optional[str] = None):
        img_url = await self.resolve_image(ctx, target)
        quoted = urllib.parse.quote(img_url, safe='')
        url = f"https://frenchnoodles.xyz/api/endpoints/trash?image={quoted}"
        await ctx.reply(url, mention_author=False)

async def setup(bot):
    await bot.add_cog(Manipulation(bot))
