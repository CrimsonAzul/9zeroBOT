import os
import asyncio
import aiohttp
import discord
from discord.ext import commands
from discord.ext import tasks
import difflib
class ReusableSession:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
import json
from datetime import datetime
import pytz
import urllib
import re
import random
import time
import html
import xml.etree.ElementTree as ET
from safe_math import safe_calculate, CalcError


def _fetch_rl_sync(platform: str, username: str):
    from curl_cffi import requests
    url = f"https://api.tracker.gg/api/v2/rocket-league/standard/profile/{platform}/{urllib.parse.quote(username)}"
    resp = requests.get(url, impersonate="chrome", timeout=15)
    if resp.status_code == 404:
        return 404, None
    if resp.status_code != 200:
        return resp.status_code, None
    return 200, resp.json()


class RocketLeagueView(discord.ui.View):
    def __init__(self, author_id: int, embed_p1: discord.Embed, embed_p2: discord.Embed, profile_url: str = None):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.embed_p1 = embed_p1
        self.embed_p2 = embed_p2

        if profile_url:
            self.add_item(discord.ui.Button(label="TRN Profile", url=profile_url, style=discord.ButtonStyle.link))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Had l buttons mashi dyalek!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Competitive & Stats", style=discord.ButtonStyle.primary, emoji="🏆", disabled=True)
    async def page_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_one.disabled = True
        self.page_two.disabled = False
        await interaction.response.edit_message(embed=self.embed_p1, view=self)

    @discord.ui.button(label="Extra Modes", style=discord.ButtonStyle.secondary, emoji="🎮")
    async def page_two(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_one.disabled = False
        self.page_two.disabled = True
        await interaction.response.edit_message(embed=self.embed_p2, view=self)


class GlobUtil(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Start background check loop for reminders
        self.check_reminders.start()

    async def cog_load(self):
        await self.init_db()

    def cog_unload(self):
        self.check_reminders.cancel()

    async def init_db(self):
        async with self.bot.db.execute("CREATE TABLE IF NOT EXISTS reminders (user_id INTEGER, channel_id INTEGER, reminder_text TEXT, end_time INTEGER)"):
            await self.bot.db.commit()
        async with self.bot.db.execute("CREATE INDEX IF NOT EXISTS idx_reminders_end_time ON reminders (end_time)"):
            await self.bot.db.commit()

    @commands.command(name="makegif", aliases=["togif"], help="3tini video nreddo GIF.")
    async def makegif(self, ctx):
        if not ctx.message.attachments:
            await ctx.send("3tini chy video nredo GIF.")
            return

        attachment = ctx.message.attachments[0]

        if not attachment.content_type or not attachment.content_type.startswith('video/'):
            await ctx.send("3tini video mgad..")
            return

        input_video = f"video_{ctx.message.id}.mp4"
        output_gif = f"converted_{ctx.message.id}.gif"

        wait_embed = discord.Embed(
            description="Sber 3lia...",
            color=0x000000
        )
        wait_msg = await ctx.send(embed=wait_embed)

        try:
            video_data = await attachment.read()
            with open(input_video, "wb") as f:
                f.write(video_data)

            def convert():
                from moviepy.video.io.VideoFileClip import VideoFileClip
                with VideoFileClip(input_video) as clip:
                    # Native v2.x method to resize dimensions down and save space
                    if clip.w > 480:
                        clip = clip.resized(width=480)

                    # Strictly standard arguments to avoid keyword conflicts
                    clip.write_gif(
                        output_gif,
                        fps=10,
                        logger=None
                    )

            await asyncio.to_thread(convert)

            await ctx.send(file=discord.File(output_gif))
            await wait_msg.delete()


        except Exception as e:
            err_embed = discord.Embed(
                description=f"Tra chy mochkil :/ `{e}`",
                color=0x000000
            )
            await wait_msg.edit(embed=err_embed)

        finally:
            for filepath in (input_video, output_gif):
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
            import gc
            gc.collect()

    @commands.command(name="image", aliases=['img', "tsawr", "tsawer"], help="Njbed lik tsawr mn google.")
    async def image(self, ctx, *, query: str):
        wait_embed = discord.Embed(
            description=f"Sbr 3lia...",
            color=0x000000
        )
        status_msg = await ctx.send(embed=wait_embed)

        params = {
            'api_key': os.getenv('IMAGE_KEY'),
            'q': query,
            'search_type': 'images',
            'location': 'United States'
        }

        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get('https://api.scaleserp.com/search', params=params) as resp:
                    if resp.status != 200:
                        raise Exception(f"API 3tani code {resp.status}")
                    data = await resp.json()

            image_results = data.get('image_results', [])
            if not image_results:
                await status_msg.edit(
                    embed=discord.Embed(description="Mal9it ta tswira ._.", color=0x000000))
                return

            embed_pages = []
            for item in image_results:
                img_url = item.get('image')
                title = item.get('title', 'Image Search Result')
                source_link = item.get('link', '')

                if img_url:
                    embed = discord.Embed(
                        title=title[:256],
                        url=source_link if source_link.startswith("http") else None,
                        color=0x000000
                    )
                    embed.set_image(url=img_url)
                    embed_pages.append(embed)

            if not embed_pages:
                await status_msg.edit(embed=discord.Embed(description="Tswira fiha chy mochkil.", color=0x000000))
                return


            view = self.bot.Paginator(ctx, pages=embed_pages)
            initial_embed = view.get_page()

            await status_msg.edit(embed=initial_embed, view=view)
            view.message = status_msg

        except Exception as e:
            err_embed = discord.Embed(
                description=f"Chy 7aja mahiyach smo7at. :(\n`{e}`",
                color=0x000000
            )
            await status_msg.edit(embed=err_embed)

    @commands.command(name="dictionary", aliases=["definition", "define", "chre7", "chr7", "dict"], help="Njbed lik ay definition mn Urban Dictionary")
    async def dictionary(self, ctx, *, search: str):

        search_query = search.replace(" ", "+")
        url = f"http://api.urbandictionary.com/v0/define?term={search_query}"

        wait_embed = discord.Embed(
            description=f"Sbr 3lia...",
            color=0x000000
        )
        status_msg = await ctx.send(embed=wait_embed)

        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise Exception(f"API 3tani code {resp.status}")
                    data = await resp.json()

            results = data.get("list", [])
            if not results:
                await status_msg.edit(
                    embed=discord.Embed(description=f"Mal9itch definition ta3 **{search}**.", color=0x000000))
                return

            embed_pages = []
            for item in results:
                definition = item.get("definition", "No definition provided.")
                example = item.get("example", "No example provided.")
                thumbs_up = item.get("thumbs_up", 0)
                thumbs_down = item.get("thumbs_down", 0)


                clean_def = definition.replace("[", "").replace("]", "")
                clean_ex = example.replace("[", "").replace("]", "")


                if len(clean_def) > 1024:
                    clean_def = clean_def[:1021] + "..."
                if len(clean_ex) > 1024:
                    clean_ex = clean_ex[:1021] + "..."

                description = f"\n**Definition:**\n{clean_def}\n\n**Example:**\n*{clean_ex}*\n"

                em = discord.Embed(
                    title=f'"{search}" fl Urban Dictionary',
                    color=0x000000,
                    description=description,
                    timestamp=ctx.message.created_at
                )
                em.set_footer(text=f"👍 {thumbs_up} | 👎 {thumbs_down}")

                embed_pages.append(em)


            view = self.bot.Paginator(ctx, pages=embed_pages)
            initial_embed = view.get_page()

            await status_msg.edit(embed=initial_embed, view=view)
            view.message = status_msg

        except Exception as e:
            err_embed = discord.Embed(
                description=f"Chy 7aja mahiyach smo7at. :(\n`{e}`",
                color=0x000000
            )
            await status_msg.edit(embed=err_embed)

    @commands.command(aliases=["3alam", "raya", "country"], help="Flag ta3 ay dawla.")
    async def flag(self, ctx, *, country: str):

        code_clean = country.strip().lower()

        if code_clean == "tajda":
            url = "https://cdn.discordapp.com/attachments/1522282041738002465/1522382935188177037/20260703_002525.jpg?ex=6a484518&is=6a46f398&hm=4fcaea72fb7bb378f13bfa036be9abf907fa5978a050bbe4ca5a5ac86ba24bdb&"
            em = discord.Embed(color=0x000000)
            em.set_image(url=url)
            await ctx.send(embed=em)
            return

        elif code_clean == "israel":
            code_clean = "palestine"


        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get("https://flagcdn.com/en/codes.json") as resp:
                    if resp.status == 200:
                        countries_map = await resp.json()
                    else:
                        raise Exception()
        except Exception:
            countries_map = {"ma": "Morocco", "us": "United States", "fr": "France"}

        name_to_code = {name.lower(): code for code, name in countries_map.items()}

        if code_clean in countries_map:
            final_code = code_clean
        else:
            possible_names = list(name_to_code.keys())
            matches = difflib.get_close_matches(code_clean, possible_names, n=1, cutoff=0.4)

            if matches:
                matched_name = matches[0]
                final_code = name_to_code[matched_name]
            else:
                await ctx.send("Mal9itch had lblad.")
                return

        url = f"https://flagcdn.com/w640/{final_code}.png"

        em = discord.Embed(color=0x000000)
        em.set_image(url=url)

        matched_formal_name = countries_map[final_code]
        em.set_footer(text=f"Matched: {matched_formal_name}")

        await ctx.send(embed=em)

    @commands.command(aliases=["jow", "temp", "temperature"], help="7alat ta9s f ay mdina.")
    async def weather(self, ctx, city: str = None):
        if city == None:
            await ctx.send("Ina mdina?")
        else:
            key = os.getenv("WEATHER_KEY")
            async with self.bot.session.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}") as resp:
                r = await resp.json()
            weather = r["weather"][0]["main"]
            description = r["weather"][0]["description"]
            icon = r["weather"][0]["icon"]
            thumbnail = f"http://openweathermap.org/img/wn/{icon}@2x.png"
            name = r["name"]
            country = r["sys"]["country"]
            temp = r["main"]["temp"]
            temperature = int(temp) - 273.15
            tempee = "{:.1f}".format(temperature)
            humidity = r["main"]["humidity"]
            url = f"https://flagsapi.com/{country}/flat/64.png"
            e = discord.Embed(title=f"Weather in {name}",
                              description=f"**{str(tempee)}°C**\n"
                                          f"**{weather}** _{description}_\n"
                                          f"{humidity}% Humidity",
                              timestamp=ctx.message.created_at,
                              color=0x000000)
            e.set_footer(text=f"{name} | {country}", icon_url=url)
            e.set_thumbnail(url=thumbnail)
            await ctx.send(embed=e)

    @commands.command(name="time", aliases=["timezone", "sa3a"], help="Sa3a f ay mdina.")
    async def time(self, ctx, *, city: str = None):

        if city is None:
            local_tz = pytz.timezone("Africa/Casablanca")
            now = datetime.now(local_tz)
            time_str = now.strftime("%H:%M:%S")
            date_str = now.strftime("%Y-%m-%d")

            em = discord.Embed(
                title="Sa3a flmghrib.",
                description=f"**Time:** {time_str}\n**Date:** {date_str}",
                color=0x000000
            )
            await ctx.send(embed=em)

        else:
            city_clean = city.strip().lower().replace(" ", "_")

            matched_zone = None
            for zone in pytz.all_timezones:
                if city_clean in zone.lower():
                    matched_zone = zone
                    break

            if not matched_zone:
                await ctx.send(f"Mal9itch chy mdina smitha `{city}`.")
                return

            target_tz = pytz.timezone(matched_zone)
            now = datetime.now(target_tz)

            time_str = now.strftime("%H:%M:%S")
            date_str = now.strftime("%Y-%m-%d")
            display_zone = matched_zone.replace("_", " ")

            em = discord.Embed(
                title=f"Sa3a f {display_zone}",
                description=f"**Time:** {time_str}\n**Date:** {date_str}",
                color=0x000000
            )
            em.set_footer(text=f"UTC Offset: {now.strftime('%z')}")

            await ctx.send(embed=em)

    @commands.command(aliases=["trans", "trjm", "trjem", "terjem"], help="Nterjem lik ay 7aja.")
    async def translate(self, ctx, fromlang, tolang, *, text):
        if not hasattr(self, "_google_translator") or self._google_translator is None:
            from googletrans import Translator
            self._google_translator = Translator()
        translation = await self._google_translator.translate(text, src=fromlang, dest=tolang)
        e = discord.Embed(title=f"Terjama men ({fromlang}) l ({tolang})",
                           color=0x000000,
                           timestamp=ctx.message.created_at,
                           description=f"```{translation.text}```")
        await ctx.send(embed=e)

    @commands.command(aliases=['yt'], help="N9elleb lik f youtube.")
    async def youtube(self, ctx, *, search):
        string = urllib.parse.urlencode({'search_query': search})
        async with self.bot.session.get('https://www.youtube.com/results?' + string) as resp:
            html_content = await resp.text()
        results = re.findall(r'/watch\?v=(.{11})', html_content)
        video = "https://www.youtube.com/watch?v=" + results[0]
        await ctx.send(video)

    @commands.command(aliases=["calc", "7sb", "7seb"], help="N7seb lik lmath sahel.")
    async def calculate(self, ctx, *, operation):
        try:
            result = safe_calculate(operation)
        except CalcError as e:
            return await ctx.send(f"Mochkil: {e}")
        text = str(result)
        if len(text) > 1900:
            text = text[:1900] + "..."
        await ctx.send(f"`{text}`")

    @commands.command(name="rhyme", aliases=["rhymes", "9afiya"], help="Njbed lik lkelmat li 3endhom nafs l 9afiya.")
    async def rhyme(self, ctx, word: str):

        url = f"https://api.datamuse.com/words?rel_rhy={word}"

        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await ctx.send("Tra chy mochkil m3a l API.")
                        return
                    data = await resp.json()
        except Exception:
            await ctx.send("Tra chy mochkil fl API.")
            return

        words = [item["word"] for item in data if "word" in item]

        if not words:
            await ctx.send("Mal9it walo hh.")
            return

        view = self.bot.Paginator(
            ctx,
            pages=words,
            per_page=15,
            title=f'Lkelmat li 3ndhom 9afiya m3a "{word}"'
        )

        initial_embed = view.get_page()
        status_msg = await ctx.send(embed=initial_embed, view=view)
        view.message = status_msg

    @commands.command(aliases=["ip", "doxx", "location"], help="Nl9a lik location ta3 ay IP address.")
    async def locate(self, ctx, ip: str):
        async with self.bot.session.get(f"http://ip-api.com/json/{ip}") as resp:
            r = await resp.json()
        status = r["status"]
        if status == 'success':
            country = r["country"]
            code = r["countryCode"]
            region = r["region"]
            rname = r["regionName"]
            city = r["city"]
            zip = r["zip"]
            timezone = r["timezone"]
            isp = r["isp"]
            AS = r["as"]
            e = discord.Embed(title=f"Location ta3: {r['query']}",
                               description=f"**Country** {country} / {code}\n"
                                           f"**Region** {rname} / {region}\n"
                                           f"**City** {city}\n"
                                           f"**ZIP** {zip}\n"
                                           f"**Timezone** {timezone}\n"
                                           f"**ISP** {isp}\n"
                                           f"**AS** {AS}",
                               color=0x000000,
                               timestamp=ctx.message.created_at)
            await ctx.send(embed=e)
        else:
            await ctx.send("dak l IP mal9itouch :/")

    @commands.command(name="reverse", aliases=["reverseimage"], help="3tini tswira n9elleb lik 3liha fl web.")
    async def reverse(self, ctx, user_or_image: str = None):

        if user_or_image:
            if "http" in user_or_image:
                image = user_or_image
            else:
                try:
                    member = await commands.UserConverter().convert(ctx, user_or_image)
                    image = member.display_avatar.url
                except Exception:
                    await ctx.send("3tini ya tswira, ya lien ta3 tswira wla pingi chy wa7d.")
                    return
        else:
            if len(ctx.message.attachments) > 0:
                image = ctx.message.attachments[0].url
            else:
                await ctx.send("3tini ya tswira, ya lien ta3 tswira wla pingi chy wa7d.")
                return

        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))

        try:
            import serpapi
            params = {
                "engine": "google_lens",
                "url": image,
                "api_key": os.getenv('SERPAPI_KEY')
            }

            search = serpapi.GoogleSearch(params)
            results = search.get_dict()

            matches = results.get('visual_matches', [])
            links = [item['link'] for item in matches if 'link' in item]

            if not links:
                await wait.edit(
                    embed=discord.Embed(description="Mal9it walo f tal9ib dyal had tswira.", color=0x000000))
                return

            view = self.bot.Paginator(
                ctx,
                pages=links,
                per_page=10,
                title=f"Had tswira l9itha f {len(links)} blasa"
            )

            initial_embed = view.get_page()
            initial_embed.set_thumbnail(url=image)

            await wait.edit(embed=initial_embed, view=view)
            view.message = wait

        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: {e}", color=0x000000))

    @commands.command(aliases=['8ball', '8b', "wach", "wash", "wax"], help="Sewelni njawbk.")
    async def eightball(self, ctx):
        responses = ["Ah", "Wayeh", "Darori", "Rah bayna", "Btabi3t l7al", "M3rofa hadi", "Ayeh kayna", "Bss7",
                     "La", "Maymknch", "Mosta7il", "Gher katkhrbe9", "Ma so2al ma walo", "Mandmench lik", "S3eb",
                     "Mo7al", "Momkin", "Ghaliban", "Ma3rftch sara7a", "3la 7sab", "Allah A3lam"]
        await ctx.reply(random.choice(responses), mention_author=False)

    @commands.command(help="N9elleb lik 3la gif.")
    async def gif(self, ctx, *, q="None"):
        query_encoded = urllib.parse.quote(q)
        url = f"https://tenor.com/search/{query_encoded}-gifs"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        try:
            async with self.bot.session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    text_content = await resp.text()
                    media_urls = re.findall(r'https://media\.tenor\.com/[^\s\"\'\>]+', text_content)
                gifs = list(set([u for u in media_urls if u.endswith('.gif')]))
                if gifs:
                    gif = random.choice(gifs)
                    await ctx.send(gif)
                    return
            await ctx.send(f"Malkitch chy gif l `{q}`.")
        except Exception as e:
            await ctx.send(f"Mochkil: {e}")

    @commands.command(aliases=['cf', 'drhm', 'drhem'], help="Nlou7 derhem o nchouf wach jat ras wla njema.")
    async def coinflip(self, ctx):
        choices = [':coin: njma (tails)', ':coin: ras (heads)']
        await ctx.send(random.choice(choices))

    @commands.command(aliases=["ye", "kanye", "quote"], help="Quotes ta3 Kanye West.")
    async def kanyequote(self, ctx):
        async with self.bot.session.get("https://api.kanye.rest/") as resp:
            quote_data = await resp.json()
        quote = quote_data["quote"]
        await ctx.send(f'"{quote}" -Kanye West')

    @commands.command(aliases=["nrd"], help="Lo7 dice o chouf ch7al jak.")
    async def dice(self, ctx):
        dice = [1, 2, 3, 4, 5 , 6]
        await ctx.send(f"🎲 {random.choice(dice)}")

    @commands.command(help="N3tik informations 3la ay anime.")
    async def anime(self, ctx, *, anime: str):
        anime = anime.lower().replace(" ", "%20")
        async with self.bot.session.get(f"https://kitsu.io/api/edge/anime?filter[text]={anime}") as resp:
            anime_data = await resp.json()
        r = anime_data['data'][0]
        type = r['type']
        description = r['attributes']['description']
        titleen = r['attributes']['titles']['en']
        titleja = r['attributes']['titles']['en_jp']
        status = r['attributes']['status']
        start = r['attributes']['startDate']
        end = r['attributes']['endDate']
        poster = r['attributes']['posterImage']['large']
        episodes = r['attributes']['episodeCount']
        e = discord.Embed(title=titleen, color=0x000000, timestamp=ctx.message.created_at)
        e.add_field(name="Japanese Title", value=titleja)
        e.add_field(name="Type", value=type)
        e.add_field(name="Status", value=status)
        e.add_field(name="Start Date", value=start)
        e.add_field(name="End Date", value=end)
        e.add_field(value=episodes, name="Episodes")
        e.add_field(name="Description", value=description)
        e.set_image(url=poster)
        await ctx.send(embed=e)

    @commands.command(name="github", aliases=["gh"], help="Njbed lik details ta3 user f github.")
    async def github(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        url = f"https://api.github.com/users/{username}"
        headers = {"User-Agent": "SifdineBot"}
        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f GitHub: `{username}`", color=0x000000))
                        return
                    if resp.status != 200:
                        raise Exception(f"HTTP Code {resp.status}")
                    data = await resp.json()

            name = data.get("name") or data.get("login")
            bio = data.get("bio") or "Nsit ndir bio hh."
            followers = data.get("followers", 0)
            following = data.get("following", 0)
            public_repos = data.get("public_repos", 0)
            avatar_url = data.get("avatar_url")
            html_url = data.get("html_url")
            location = data.get("location") or "Hidden"
            company = data.get("company") or "No company"
            created_at_str = data.get("created_at")

            created_date = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")

            embed = discord.Embed(
                title=f"GitHub Profile ta3 {name}",
                url=html_url,
                description=bio,
                color=0x000000
            )
            embed.set_thumbnail(url=avatar_url)
            embed.add_field(name="Followers", value=str(followers), inline=True)
            embed.add_field(name="Following", value=str(following), inline=True)
            embed.add_field(name="Public Repos", value=str(public_repos), inline=True)
            embed.add_field(name="Location", value=location, inline=True)
            embed.add_field(name="Company", value=company, inline=True)
            embed.add_field(name="Created", value=created_date, inline=True)

            await wait.edit(embed=embed)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))

    @commands.command(name="reddit", help="Chouf chy profile f reddit.")
    async def reddit(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        headers = {
            "User-Agent": "SifdineBot/1.0",
            "Accept": "application/json",
        }
        token = os.getenv("REDDIT_BOT_TOKEN")
        if token:
            headers["Authorization"] = f"bearer {token}"

        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(
                    f"https://oauth.reddit.com/user/{username}/about",
                    headers=headers,
                ) as resp:
                    if resp.status == 404:
                        await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f Reddit: `{username}`", color=0x000000))
                        return
                    if resp.status == 401 or resp.status == 403:
                        msg = (f"Mochkil f Token. Error code: `{resp.status}`")
                        await wait.edit(embed=discord.Embed(description=msg, color=0x000000))
                        return
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")

                    data = await resp.json()
                    user = data.get("data", {})

            name = user.get("name") or username
            title = user.get("subreddit", {}).get("title")
            description = user.get("subreddit", {}).get("public_description") or "No description"
            avatar = user.get("snoovatar_img")
            if not avatar:
                avatar = user.get("icon_img") or user.get("avatar_img")
            if avatar and avatar.startswith("https"):
                avatar = avatar
            link_karma = user.get("link_karma", 0)
            comment_karma = user.get("comment_karma", 0)
            total_karma = user.get("total_karma", link_karma + comment_karma)
            is_gold = user.get("is_gold", False)
            is_employee = user.get("is_employee", False)
            verified = user.get("verified", False)
            created_utc = user.get("created_utc")
            created_date = datetime.fromtimestamp(created_utc, pytz.utc).strftime("%Y-%m-%d") if created_utc else "Hidden"

            profile_url = f"https://www.reddit.com/user/{username}"

            embed = discord.Embed(
                title=f"Reddit Profile: {name}" + (" 🏆" if is_gold or is_employee else ""),
                url=profile_url,
                description=description,
                color=0x000000,
            )
            if avatar:
                clean_avatar = avatar.split('?')[0]
                embed.set_thumbnail(url=clean_avatar)

            embed.add_field(name="Link Karma", value=f"**{link_karma}**", inline=True)
            embed.add_field(name="Comment Karma", value=f"**{comment_karma}**", inline=True)
            embed.add_field(name="Total Karma", value=f"**{total_karma}**", inline=True)
            embed.add_field(name="Verified", value="Yes ✅" if verified else "No", inline=True)
            embed.add_field(name="Reddit Employee", value="Yes" if is_employee else "No", inline=True)
            embed.add_field(name="Created", value=created_date, inline=True)

            await wait.edit(embed=embed)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))

    @commands.command(name="tiktok", aliases=["tt"], help="Chouf chy profile f TikTok.")
    async def tiktok(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        
        # Load available API keys
        keys = [os.getenv(f'RAPID_API_KEY_{i}') for i in range(1, 3)]
        keys = [k for k in keys if k]
        
        if not keys:
            await wait.edit(embed=discord.Embed(description="TikTok API keys not configured.", color=0x000000))
            return
            
        # Shuffle to start with a random key
        random.shuffle(keys)

        url = "https://tiktok-scraper7.p.rapidapi.com/user/info"
        params = {"unique_id": username}
        
        data = None
        for api_key in keys:
            headers = {
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": "tiktok-scraper7.p.rapidapi.com"
            }
            
            try:
                async with ReusableSession(self.bot.session) as session:
                    async with session.get(url, headers=headers, params=params) as resp:
                        # Check rate limits in headers
                        remaining = int(resp.headers.get("X-RateLimit-Requests-Remaining", 1))
                        
                        # If 429 or quota exhausted, try next key
                        if resp.status == 429 or remaining <= 0:
                            continue
                            
                        if resp.status != 200:
                            raise Exception(f"API returned status {resp.status}")
                            
                        data = await resp.json()
                        break # Success, stop trying other keys
            except Exception:
                continue # Try next key

        if not data:
            await wait.edit(embed=discord.Embed(description="Tra chy mochkil: Salat l Quota wla chi mochkil fl API.", color=0x000000))
            return

        # Parsing the successful response structure
        user_data = data.get("data", {}).get("user", {})
        stats = data.get("data", {}).get("stats", {})
        
        if not user_data:
            await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f TikTok: `{username}`", color=0x000000))
            return
        
        nickname = user_data.get("nickname", "Unknown")
        unique_id = user_data.get("uniqueId", username)
        bio = user_data.get("signature", "No bio.")
        followers = stats.get("followerCount", 0)
        following = stats.get("followingCount", 0)
        heart_count = stats.get("heartCount", 0)
        
        embed = discord.Embed(
            title=f"TikTok Profile: {nickname} (@{unique_id})",
            description=bio,
            color=0x000000
        )
        if user_data.get("avatarMedium"):
            embed.set_thumbnail(url=user_data.get("avatarMedium"))
        embed.add_field(name="Followers", value=f"{followers:,}", inline=True)
        embed.add_field(name="Following", value=f"{following:,}", inline=True)
        embed.add_field(name="Likes", value=f"{heart_count:,}", inline=True)
        
        await wait.edit(embed=embed)

    @commands.command(name="instagram", aliases=["insta", "ig"], help="Chouf chy profile f Instagram.")
    async def instagram(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        
        # Load available API keys
        keys = [os.getenv(f'RAPID_API_KEY_{i}') for i in range(1, 3)]
        keys = [k for k in keys if k]
        
        if not keys:
            await wait.edit(embed=discord.Embed(description="Instagram API keys not configured.", color=0x000000))
            return
            
        # Shuffle to start with a random key
        random.shuffle(keys)

        url = "https://instagram-looter2.p.rapidapi.com/profile2"
        params = {"username": username}
        
        data = None
        for api_key in keys:
            headers = {
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": "instagram-looter2.p.rapidapi.com",
                "Content-Type": "application/json"
            }
            
            try:
                async with ReusableSession(self.bot.session) as session:
                    async with session.get(url, headers=headers, params=params) as resp:
                        if resp.status == 429:
                            continue
                            
                        if resp.status != 200:
                            continue
                            
                        data = await resp.json()
                        if data:
                            break
            except Exception:
                continue

        if not data:
             await wait.edit(embed=discord.Embed(description=f"Ma 9dertch njbed l info dyal `{username}`.", color=0x000000))
             return
        
        # Adjust fields based on the new API's response structure
        # (Found: follower_count, following_count, media_count)
        # Using 0 as default if the value is None
        def format_count(val):
            return f"{val:,}" if val is not None else "0"

        embed = discord.Embed(
            title=f"Instagram Profile: {data.get('username', username)}",
            url=f"https://instagram.com/{data.get('username', username)}",
            color=0x000000
        )
        embed.set_thumbnail(url=data.get("profile_pic_url"))
        embed.add_field(name="Full Name", value=data.get("full_name", "N/A"), inline=True)
        embed.add_field(name="Verified", value="Yes" if data.get("is_verified") else "No", inline=True)
        embed.add_field(name="Private", value="Yes" if data.get("is_private") else "No", inline=True)
        embed.add_field(name="Followers", value=format_count(data.get('follower_count')), inline=True)
        embed.add_field(name="Following", value=format_count(data.get('following_count')), inline=True)
        embed.add_field(name="Posts", value=format_count(data.get('media_count')), inline=True)
        embed.add_field(name="Biography", value=data.get("biography", "N/A"), inline=False)
        
        await wait.edit(embed=embed)

    @commands.command(name="twitter", aliases=["x"], help="Chouf chy profile f Twitter (X).")
    async def twitter(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        
        # Load available API keys
        keys = [os.getenv(f'RAPID_API_KEY_{i}') for i in range(1, 3)]
        keys = [k for k in keys if k]
        
        if not keys:
            await wait.edit(embed=discord.Embed(description="Twitter API keys not configured.", color=0x000000))
            return
            
        # Shuffle to start with a random key
        random.shuffle(keys)

        url = "https://twitter-api45.p.rapidapi.com/screenname.php"
        params = {"screenname": username}
        
        data = None
        for api_key in keys:
            headers = {
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": "twitter-api45.p.rapidapi.com",
                "Content-Type": "application/json"
            }
            
            try:
                async with ReusableSession(self.bot.session) as session:
                    async with session.get(url, headers=headers, params=params) as resp:
                        if resp.status == 429:
                            continue
                            
                        if resp.status != 200:
                            continue
                            
                        data = await resp.json()
                        if data:
                            break
            except Exception:
                continue

        if not data:
             await wait.edit(embed=discord.Embed(description=f"Ma 9dertch njbed l info dyal `{username}`.", color=0x000000))
             return
        
        # Use existing format_count helper
        def format_count(val):
            return f"{val:,}" if val is not None else "0"

        embed = discord.Embed(
            title=f"Twitter Profile: @{data.get('profile', username)}",
            url=f"https://twitter.com/{data.get('profile', username)}",
            color=0x000000
        )
        # Attempt to get higher resolution avatar
        avatar_url = data.get("avatar", "")
        if avatar_url:
            # Common Twitter avatar suffixes to remove for higher res
            high_res_avatar = avatar_url.replace("_normal.jpg", ".jpg").replace("_bigger.jpg", ".jpg").replace("_mini.jpg", ".jpg")
            embed.set_thumbnail(url=high_res_avatar)
        embed.add_field(name="Full Name", value=data.get("name", "N/A"), inline=True)
        embed.add_field(name="Verified", value="Yes" if data.get("blue_verified") else "No", inline=True)
        embed.add_field(name="Location", value=data.get("location") or "N/A", inline=True)
        embed.add_field(name="Followers", value=format_count(data.get('sub_count')), inline=True)
        embed.add_field(name="Following", value=format_count(data.get('friends')), inline=True)
        # Note: The API only provides 'statuses_count' (total activity).
        embed.add_field(name="Total Activity", value=format_count(data.get('statuses_count')), inline=True)
        embed.add_field(name="Biography", value=data.get("desc", "N/A"), inline=False)
        
        await wait.edit(embed=embed)

    @commands.command(name="download", aliases=["dl", "save"], help="Ntelechargi lik video mn TikTok, Instagram, wla YouTube Shorts.")
    async def download(self, ctx, url: str):
        url = url.strip("<>")
        if not re.match(r"^https?://", url, re.IGNORECASE):
            return await ctx.send(embed=discord.Embed(description="Mochkil: 3tini link s7i7 (khasso ybda b http:// wla https://).", color=0x000000))

        wait = await ctx.send(embed=discord.Embed(description="Sber chwia...", color=0x000000))
        
        filename = f"download_{ctx.message.id}"
        
        import sys
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--max-filesize", "25M",
            "-f", "best",
            "-o", f"{filename}.%(ext)s",
            "--no-check-certificate",
            "--no-warnings",
            "--quiet"
        ]
        
        if os.path.exists("cookies.txt"):
            cmd.extend(["--cookies", "cookies.txt"])

        # "--" stops yt-dlp from reading the URL as an option (e.g. "--exec ...").
        cmd.extend(["--", url])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except:
                    pass
                await wait.edit(embed=discord.Embed(description="Mochkil: Tfawat lwe9t (Timeout after 90s).", color=0x000000))
                return
            
            # Find the downloaded file
            downloaded_file = None
            for f in os.listdir("."):
                if f.startswith(filename) and not f.endswith(".part") and not f.endswith(".ytdl"):
                    downloaded_file = f
                    break
                    
            if downloaded_file and os.path.exists(downloaded_file):
                file_size = os.path.getsize(downloaded_file)
                if file_size <= 25 * 1024 * 1024:
                    await ctx.send(file=discord.File(downloaded_file))
                    await wait.delete()
                else:
                    await wait.edit(embed=discord.Embed(description="L file kber mn 25MB. Man9edch nsifto f Discord.", color=0x000000))
                try:
                    os.remove(downloaded_file)
                except:
                    pass
            else:
                if process.returncode != 0:
                    err_str = stderr.decode('utf-8', errors='ignore').strip()
                    # Clean up ANSI escape sequences if any
                    err_str = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', err_str)
                    
                    if "Sign in to confirm" in err_str:
                        description = (
                            f"**Mochkil:** YouTube blocks this download request because it thinks the bot is a scraper.\n\n"
                            f"**Solution:** Please place a valid `cookies.txt` file in the bot's root directory. "
                            f"Refer to [yt-dlp Wiki on Cookies](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) for details."
                        )
                    else:
                        description = f"Mochkil fl download:\n```\n{err_str[:1500]}\n```"
                else:
                    description = "Mochkil: Mal9itch l file ta3 download."
                
                await wait.edit(embed=discord.Embed(description=description, color=0x000000))
                
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))
        finally:
            # Cleanup any leftover files starting with filename
            for f in os.listdir("."):
                if f.startswith(filename):
                    try:
                        os.remove(f)
                    except:
                        pass
            import gc
            gc.collect()

    @commands.command(name="username", aliases=["sherlock"], help="Nchouf lik username wach available f 20 platform.")
    async def username(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description=f"Kanchekki username `{username}` f 20 platforms...", color=0x000000))

        platforms = {
            "GitHub": {"url": "https://api.github.com/users/{username}", "type": "status"},
            "Reddit": {"url": "https://www.reddit.com/user/{username}/about.json", "type": "status"},
            "Chess.com": {"url": "https://api.chess.com/pub/player/{username}", "type": "status"},
            "Scratch": {"url": "https://api.scratch.mit.edu/users/{username}", "type": "status"},
            "Docker Hub": {"url": "https://hub.docker.com/v2/users/{username}/", "type": "status"},
            "Spotify": {"url": "https://open.spotify.com/user/{username}", "type": "status"},
            "Pinterest": {"url": "https://www.pinterest.com/{username}/", "type": "status"},
            "DeviantArt": {"url": "https://www.deviantart.com/{username}", "type": "status"},
            "SoundCloud": {"url": "https://soundcloud.com/{username}", "type": "status"},
            "Twitch": {"url": "https://www.twitch.tv/{username}", "type": "status"},
            "Steam": {"url": "https://steamcommunity.com/id/{username}", "type": "steam"},
            "Linktree": {"url": "https://linktree.com/{username}", "type": "status"},
            "Letterboxd": {"url": "https://letterboxd.com/{username}/", "type": "status"},
            "DailyMotion": {"url": "https://www.dailymotion.com/{username}", "type": "status"},
            "Behance": {"url": "https://www.behance.net/{username}", "type": "status"},
            "Medium": {"url": "https://medium.com/@{username}", "type": "status"},
            "Duolingo": {"url": "https://www.duolingo.com/2017-06-30/users?username={username}", "type": "duolingo"},
            "Vimeo": {"url": "https://vimeo.com/{username}", "type": "status"},
            "NPM": {"url": "https://www.npmjs.com/~{username}", "type": "status"},
            "Patreon": {"url": "https://www.patreon.com/{username}", "type": "status"}
        }

        async def check_platform(session, name, config, u):
            url = config["url"].format(username=u)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
            try:
                if config["type"] == "status":
                    async with session.get(url, headers=headers, timeout=8) as resp:
                        if resp.status == 404:
                            return name, "Available"
                        elif resp.status in [200, 301, 302]:
                            return name, "Taken"
                        else:
                            return name, f"Error ({resp.status})"
                elif config["type"] == "steam":
                    async with session.get(url, headers=headers, timeout=8) as resp:
                        if resp.status == 404:
                            return name, "Available"
                        html = await resp.text()
                        if "The specified profile could not be found" in html or "Error" in html:
                            return name, "Available"
                        return name, "Taken"
                elif config["type"] == "duolingo":
                    async with session.get(url, headers=headers, timeout=8) as resp:
                        if resp.status == 404:
                            return name, "Available"
                        data = await resp.json()
                        if data.get("users"):
                            return name, "Taken"
                        return name, "Available"
            except Exception:
                return name, "Error"

        async with ReusableSession(self.bot.session) as session:
            tasks = [check_platform(session, name, config, username) for name, config in platforms.items()]
            results = await asyncio.gather(*tasks)

        lines = []
        for name, status in results:
            icon = "✅" if status == "Available" else "❌" if status == "Taken" else "⚠️"
            lines.append(f"{icon} **{name}**: {status}")

        half = len(lines) // 2
        col1 = "\n".join(lines[:half])
        col2 = "\n".join(lines[half:])

        embed = discord.Embed(
            title=f"Username Check: `{username}`",
            color=0x000000
        )
        embed.add_field(name="Platforms (1-10)", value=col1, inline=True)
        embed.add_field(name="Platforms (11-20)", value=col2, inline=True)

        await wait.edit(embed=embed)

    @commands.command(name="minecraft", aliases=["mc", "namemc"], help="Chouf chy profile f Minecraft (NameMC).")
    async def minecraft(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        url = f"https://playerdb.co/api/player/minecraft/{username}"
        headers = {"User-Agent": "SifdineBot"}
        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f Minecraft: `{username}`", color=0x000000))
                        return
                    if resp.status != 200:
                        raise Exception(f"HTTP Code {resp.status}")
                    data = await resp.json()

            if not data.get("success"):
                await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f Minecraft: `{username}`", color=0x000000))
                return

            player_data = data["data"]["player"]
            uuid = player_data["id"]
            current_name = player_data["username"]
            meta = player_data.get("meta", {})
            name_history_raw = meta.get("name_history", [])

            history_list = []
            for idx, hist in enumerate(name_history_raw):
                history_list.append(f"{idx+1}. {hist.get('name')}")

            history_str = "\n".join(history_list) if history_list else "Walo history."
            if len(history_str) > 1024:
                history_str = history_str[:1020] + "..."

            embed = discord.Embed(
                title=f"Minecraft Profile: {current_name}",
                url=f"https://namemc.com/profile/{uuid}",
                description=f"**Name History:**\n{history_str}",
                color=0x000000
            )
            embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{uuid}/128")
            embed.set_image(url=f"https://mc-heads.net/body/{uuid}/256")
            embed.add_field(name="UUID", value=f"`{uuid}`", inline=False)
            embed.add_field(name="Skins & Customizations", value=f"[Skin URL](https://mc-heads.net/skin/{uuid})", inline=False)
            embed.set_footer(text="Mojang name history restrictions may apply.")

            await wait.edit(embed=embed)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))

    @commands.command(name="roblox", aliases=["roblok"], help="Chouf chy user f Roblox.")
    async def roblox(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        try:
            resolve_url = "https://users.roblox.com/v1/usernames/users"
            payload = {"usernames": [username], "excludeBannedUsers": False}

            async with ReusableSession(self.bot.session) as session:
                async with session.post(resolve_url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        raise Exception(f"Roblox username resolution failed with code {resp.status}")
                    search_data = await resp.json()

            user_list = search_data.get("data", [])
            if not user_list:
                await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f Roblox: `{username}`", color=0x000000))
                return

            user_id = user_list[0]["id"]

            detail_url = f"https://users.roblox.com/v1/users/{user_id}"
            avatar_url = f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=352x352&format=Png&isCircular=false"

            async with ReusableSession(self.bot.session) as session:
                async with session.get(detail_url, headers=headers) as resp_detail, \
                           session.get(avatar_url, headers=headers) as resp_avatar:

                    if resp_detail.status != 200 or resp_avatar.status != 200:
                        raise Exception("Roblox APIs were not responsive.")

                    details = await resp_detail.json()
                    avatar_data = await resp_avatar.json()

            display_name = details.get("displayName")
            real_name = details.get("name")
            bio = details.get("description") or "Walo bio."
            created_at_str = details.get("created")

            created_date = created_at_str.split("T")[0] if created_at_str else "Hidden"

            thumb_url = None
            avatar_list = avatar_data.get("data", [])
            if avatar_list:
                thumb_url = avatar_list[0].get("imageUrl")

            embed = discord.Embed(
                title=f"Roblox Profile: {display_name} (@{real_name})",
                url=f"https://www.roblox.com/users/{user_id}/profile",
                description=bio,
                color=0x000000
            )
            if thumb_url:
                embed.set_image(url=thumb_url)

            embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
            embed.add_field(name="Created", value=created_date, inline=True)

            await wait.edit(embed=embed)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))

    @commands.command(name="chess", aliases=["chessprofile", "chessuser"], help="Chouf chy profile f Chess.com.")
    async def chess(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        headers = {"User-Agent": "SifdineBot"}
        profile_url = f"https://api.chess.com/pub/player/{username}"
        stats_url = f"https://api.chess.com/pub/player/{username}/stats"

        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(profile_url, headers=headers) as resp_profile, \
                           session.get(stats_url, headers=headers) as resp_stats:

                    if resp_profile.status == 404:
                        await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f Chess.com: `{username}`", color=0x000000))
                        return
                    if resp_profile.status != 200 or resp_stats.status != 200:
                        raise Exception("Chess.com APIs were not responsive.")

                    profile = await resp_profile.json()
                    stats = await resp_stats.json()

            name = profile.get("name") or profile.get("username")
            title = profile.get("title")
            avatar = profile.get("avatar")
            followers = profile.get("followers", 0)
            joined_timestamp = profile.get("joined")

            joined_date = datetime.fromtimestamp(joined_timestamp, pytz.utc).strftime("%Y-%m-%d") if joined_timestamp else "Hidden"

            blitz_rating = stats.get("chess_blitz", {}).get("last", {}).get("rating", "N/A")
            rapid_rating = stats.get("chess_rapid", {}).get("last", {}).get("rating", "N/A")
            bullet_rating = stats.get("chess_bullet", {}).get("last", {}).get("rating", "N/A")

            embed = discord.Embed(
                title=f"Chess.com Profile: {name}" + (f" [{title}]" if title else ""),
                url=profile.get("url"),
                color=0x000000
            )
            if avatar:
                embed.set_thumbnail(url=avatar)

            embed.add_field(name="Blitz Rating ⚡", value=f"**{blitz_rating}**", inline=True)
            embed.add_field(name="Rapid Rating ⏱️", value=f"**{rapid_rating}**", inline=True)
            embed.add_field(name="Bullet Rating ☄️", value=f"**{bullet_rating}**", inline=True)
            embed.add_field(name="Friends", value=str(followers), inline=True)
            embed.add_field(name="Created", value=joined_date, inline=True)

            await wait.edit(embed=embed)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))

    # Helper & tasks for reminders
    def parse_time(self, time_str: str) -> int:
        pattern = re.compile(r'(\d+)\s*([smhd]?)', re.IGNORECASE)
        matches = pattern.findall(time_str)
        if not matches:
            return 0
        
        total_seconds = 0
        for val, unit in matches:
            val = int(val)
            unit = unit.lower()
            if unit == 's' or unit == '':
                total_seconds += val
            elif unit == 'm':
                total_seconds += val * 60
            elif unit == 'h':
                total_seconds += val * 3600
            elif unit == 'd':
                total_seconds += val * 86400
                
        return total_seconds

    @tasks.loop(seconds=5)
    async def check_reminders(self):
        try:
            if not hasattr(self.bot, "db") or self.bot.db is None:
                return
            now = int(time.time())
            async with self.bot.db.execute(
                "SELECT rowid, user_id, channel_id, reminder_text FROM reminders WHERE end_time <= ?", 
                (now,)
            ) as cursor:
                rows = await cursor.fetchall()
            
            for rowid, user_id, channel_id, reminder_text in rows:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception:
                        pass
                if channel:
                    try:
                        await channel.send(f"<@{user_id}>, here is your reminder: {reminder_text}")
                    except Exception:
                        pass
            if rows:
                rowids = [r[0] for r in rows]
                placeholders = ",".join("?" for _ in rowids)
                async with self.bot.db.execute(f"DELETE FROM reminders WHERE rowid IN ({placeholders})", rowids):
                    await self.bot.db.commit()
        except Exception:
            pass

    @commands.command(name="reminder", aliases=["remind", "timer"], help=f"Goul lia nfekrek o sir hnnak lah.")
    async def reminder(self, ctx, time_input: str, *, message: str = "Reminder!"):
        duration = self.parse_time(time_input)
        if duration <= 0:
            await ctx.send("Mochkil: format dyal lwe9t machi howa hadak. (ex: 10m, 1h, 2d, 30s)")
            return
        
        if duration > 365 * 86400: # 1 year max
            await ctx.send("Mochkil: lwe9t kbir bzaf. (max: 1 year)")
            return

        end_time = int(time.time() + duration)
        try:
            async with self.bot.db.execute(
                "INSERT INTO reminders (user_id, channel_id, reminder_text, end_time) VALUES (?, ?, ?, ?)",
                (ctx.author.id, ctx.channel.id, message, end_time)
            ):
                await self.bot.db.commit()
            await ctx.send(f"i will remind u in <t:{end_time}:R>")
        except Exception as e:
            await ctx.send(f"Tra chy mochkil: `{e}`")

    @commands.command(name="qrcode", aliases=["qr"], help="9ad QR code mn ay text, URL wla image.")
    async def qrcode(self, ctx, *, url_or_text: str = None):
        data_to_encode = None
        if ctx.message.attachments:
            data_to_encode = ctx.message.attachments[0].url
        elif url_or_text:
            data_to_encode = url_or_text
        else:
            await ctx.send("Ya kteb chy 7aja ya 3tini tswira.")
            return

        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        
        try:
            api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(data_to_encode)}"
            async with ReusableSession(self.bot.session) as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"QR API returned status code {resp.status}")
                    img_data = await resp.read()
            
            from io import BytesIO
            file = discord.File(BytesIO(img_data), filename="qrcode.png")
            embed = discord.Embed(color=0x000000)
            embed.set_image(url="attachment://qrcode.png")
            await ctx.send(file=file, embed=embed)
            await wait.delete()
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))
        finally:
            import gc
            if 'img_data' in locals():
                del img_data
            gc.collect()

    @commands.command(name="ocr", help="Jbed text mn ay tswira.")
    async def ocr(self, ctx, *, url: str = None):
        image_url = None
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif url:
            image_url = url
        elif ctx.message.reference:
            try:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref_msg.attachments:
                    image_url = ref_msg.attachments[0].url
            except Exception:
                pass

        if not image_url:
            await ctx.send("3tini tswira wla replyi l chy message fih tswira.")
            return

        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        
        try:
            ocr_key = os.getenv("OCR_KEY", "helloworld")
            api_url = "https://api.ocr.space/parse/imageurl"
            params = {
                "apikey": ocr_key,
                "url": image_url
            }
            async with ReusableSession(self.bot.session) as session:
                async with session.get(api_url, params=params) as resp:
                    if resp.status != 200:
                        raise Exception(f"API code {resp.status}")
                    result = await resp.json()

            if result.get("OCRExitCode") != 1:
                err_msg = result.get("ErrorMessage") or "Unknown error"
                if isinstance(err_msg, list):
                    err_msg = ", ".join(err_msg)
                await wait.edit(embed=discord.Embed(description=f"Mochkil: `{err_msg}`", color=0x000000))
                return

            parsed_results = result.get("ParsedResults", [])
            if not parsed_results:
                await wait.edit(embed=discord.Embed(description="Mal9it ta ktaba f tswira.", color=0x000000))
                return

            text = parsed_results[0].get("ParsedText", "").strip()
            if not text:
                await wait.edit(embed=discord.Embed(description="Mal9it ta ktaba f tswira.", color=0x000000))
                return

            if len(text) > 2000:
                text = text[:1990] + "\n..."

            await wait.edit(content=f"Text li l9it:\n```{text}```", embed=None)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))
        finally:
            import gc
            if 'result' in locals():
                del result
            gc.collect()

    @commands.command(name="game", aliases=["steamgame"], help="Chouf chy game f steam.")
    async def game(self, ctx, *, query: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        
        search_url = f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(query)}&l=english&cc=US"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(search_url, headers=headers) as resp:
                    if resp.status != 200:
                        raise Exception(f"Steam Search returned status {resp.status}")
                    search_data = await resp.json()

            items = search_data.get("items", [])
            if not items:
                await wait.edit(embed=discord.Embed(description="Mal9it ta game b dik smiya.", color=0x000000))
                return

            appid = items[0]["id"]
            details_url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
            
            async with ReusableSession(self.bot.session) as session:
                async with session.get(details_url, headers=headers) as resp:
                    if resp.status != 200:
                        raise Exception(f"Steam Details returned status {resp.status}")
                    details_data = await resp.json()

            app_data = details_data.get(str(appid), {})
            if not app_data.get("success"):
                await wait.edit(embed=discord.Embed(description="Chy mochkil f details ta3 had l game.", color=0x000000))
                return

            data = app_data["data"]
            name = data.get("name", "Unknown Game")
            short_desc = data.get("short_description", "No description.")
            short_desc = html.unescape(re.sub(r'<[^<]+?>', '', short_desc))
            if len(short_desc) > 1024:
                short_desc = short_desc[:1021] + "..."

            is_free = data.get("is_free", False)
            price_overview = data.get("price_overview")
            price = "Free to Play" if is_free else (price_overview.get("final_formatted") if price_overview else "N/A")

            devs = ", ".join(data.get("developers", ["Unknown"]))
            release = data.get("release_date", {}).get("date", "Unknown")
            genres = ", ".join([g.get("description", "") for g in data.get("genres", [])])

            platforms_dict = data.get("platforms", {})
            platforms = []
            if platforms_dict.get("windows"):
                platforms.append("🖥️ Windows")
            if platforms_dict.get("mac"):
                platforms.append("🍎 Mac")
            if platforms_dict.get("linux"):
                platforms.append("🐧 Linux")
            platforms_str = ", ".join(platforms) if platforms else "None"

            embed = discord.Embed(
                title=name,
                url=f"https://store.steampowered.com/app/{appid}",
                description=short_desc,
                color=0x000000
            )
            header_img = data.get("header_image")
            if header_img:
                embed.set_image(url=header_img)

            embed.add_field(name="Price", value=price, inline=True)
            embed.add_field(name="Developer", value=devs, inline=True)
            embed.add_field(name="Release Date", value=release, inline=True)
            embed.add_field(name="Genres", value=genres, inline=True)
            embed.add_field(name="Platforms", value=platforms_str, inline=True)
            embed.set_footer(text=f"App ID: {appid}")

            await wait.edit(embed=embed)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))
        finally:
            import gc
            if 'search_data' in locals():
                del search_data
            if 'details_data' in locals():
                del details_data
            gc.collect()

    @commands.command(name="steam", aliases=["steamprofile", "steamuser"], help="Chouf chy profile f steam.")
    async def steam(self, ctx, identifier: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        api_key = os.environ.get("STEAM_API_KEY")
        if not api_key:
            await wait.edit(embed=discord.Embed(description="Mochkil: `STEAM_API_KEY` makaynch.", color=0x000000))
            return

        # 1. Resolve ID
        steam_id = None
        if identifier.isdigit() and len(identifier) == 17:
            steam_id = identifier
        else:
            # Check for URL
            match = re.search(r'steamcommunity\.com/(id|profiles)/([^/]+)', identifier)
            if match:
                part = match.group(2)
                if match.group(1) == 'profiles':
                    steam_id = part
                else:
                    steam_id = await self._resolve_vanity_url(part, api_key)
            else:
                # Assume vanity
                steam_id = await self._resolve_vanity_url(identifier, api_key)

        if not steam_id:
            await wait.edit(embed=discord.Embed(description="Ma9dertch nel9a  profile.", color=0x000000))
            return

        # 2. Get Data
        try:
            data = await self._get_player_data(steam_id, api_key)
            if not data:
                await wait.edit(embed=discord.Embed(description="Ma9dertch njbed l data.", color=0x000000))
                return
            
            player = data["player"]
            # Status mapping
            status_map = {
                0: "⚪ Offline",
                1: "🟢 Online",
                2: "🟡 Busy",
                3: "🟠 Away",
                4: "🔵 Snooze",
                5: "🟣 Looking to trade",
                6: "🟣 Looking to play"
            }
            status_text = status_map.get(player.get("personastate", 0), "⚪ Offline")
            
            embed = discord.Embed(
                title=player.get("personaname"),
                url=player.get("profileurl"),
                color=0x000000
            )
            embed.set_thumbnail(url=player.get("avatarfull"))
            embed.add_field(name="Status", value=status_text, inline=True)
            embed.add_field(name="Country", value=f":flag_{player.get('loccountrycode', 'aq').lower()}:" if player.get('loccountrycode') else "N/A", inline=True)
            embed.add_field(name="Profile Type", value="Public" if data["is_public"] else "Private", inline=True)
            
            if data["is_public"]:
                embed.description = f"_{data['bio']}_" if data["bio"] != "N/A" else None
                embed.add_field(name="Level", value=f"⭐ {data['level']}", inline=True)
                embed.add_field(name="Total Games", value=f"🎮 {data['games_count']}", inline=True)
                embed.add_field(name="Total Time", value=f"⏳ {data['total_playtime']}", inline=True)
                
                # Top Played
                top_played_str = "*No games found.*"
                if data["top_games"]:
                    top_played_str = "\n".join([f"• **{g['name']}** — `{g['total']:.1f} hrs`" for g in data["top_games"]])
                embed.add_field(name="🏆 Top Played Games", value=top_played_str, inline=False)
                
                # Recent Activity
                recent_str = "*No activity in the last 2 weeks.*"
                if data["recently_played"]:
                    recent_str = "\n".join([f"• **{g['name']}** — `{g['2w']:.1f} hrs`" for g in data["recently_played"]])
                embed.add_field(name="⏱️ Recent Activity (Past 2 Weeks)", value=recent_str, inline=False)
            else:
                embed.add_field(name="🔒 Privacy Notice", value="*This profile or its game details are set to private.*", inline=False)
                
            await wait.edit(embed=embed)
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: {e}", color=0x000000))

    async def _resolve_vanity_url(self, vanity_url: str, api_key: str):
        url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
        params = {"key": api_key, "vanityurl": vanity_url}
        async with self.bot.session.get(url, params=params) as resp:
            data = await resp.json()
            if data.get("response", {}).get("success") == 1:
                return data["response"]["steamid"]
            return None

    async def _get_player_data(self, steam_id: str, api_key: str):
        # 1. Player Summaries
        summaries_url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
        params = {"key": api_key, "steamids": steam_id}
        
        async with self.bot.session.get(summaries_url, params=params) as resp:
            summaries_data = await resp.json()
            players = summaries_data.get("response", {}).get("players", [])
            if not players:
                return None
            player = players[0]
        
        # 2. Bio (XML)
        bio = "N/A"
        try:
            async with self.bot.session.get(f"https://steamcommunity.com/profiles/{steam_id}/?xml=1") as resp:
                xml_text = await resp.text()
                root = ET.fromstring(xml_text)
                summary_node = root.find("summary")
                if summary_node is not None and summary_node.text:
                    bio = html.unescape(summary_node.text)[:500]
        except:
            pass

        # Public check
        is_public = player.get("communityvisibilitystate") == 3
        
        # 3. Steam Level (if public)
        level = "N/A"
        if is_public:
            level_url = "https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/"
            params = {"key": api_key, "steamid": steam_id}
            async with self.bot.session.get(level_url, params=params) as resp:
                level_data = await resp.json()
                level = level_data.get("response", {}).get("player_level", "N/A")

        # 4. Games Data (if public)
        games_count = "N/A"
        total_playtime = "N/A"
        recently_played = []
        
        if is_public:
            # Get Owned Games
            games_url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
            params = {"key": api_key, "steamid": steam_id, "include_appinfo": 1, "include_played_free_games": 1}
            async with self.bot.session.get(games_url, params=params) as resp:
                games_data = await resp.json()
                games = games_data.get("response", {}).get("games", [])
                if games:
                    games_count = len(games)
                    total_playtime = sum(g.get("playtime_forever", 0) for g in games) / 60
                    total_playtime = f"{total_playtime:.1f} hrs"
            
            # Recently Played
            rec_url = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/"
            params = {"key": api_key, "steamid": steam_id, "count": 3}
            async with self.bot.session.get(rec_url, params=params) as resp:
                rec_data = await resp.json()
                rec_games = rec_data.get("response", {}).get("games", [])
                for g in rec_games:
                    recently_played.append({
                        "name": g.get("name"),
                        "2w": g.get("playtime_2weeks", 0) / 60,
                        "total": g.get("playtime_forever", 0) / 60
                    })
            
            # Sort Top Played
            top_games = []
            if games:
                sorted_games = sorted(games, key=lambda x: x.get("playtime_forever", 0), reverse=True)
                for g in sorted_games[:3]:
                    top_games.append({
                        "name": g.get("name"),
                        "total": g.get("playtime_forever", 0) / 60
                    })

        return {
            "player": player,
            "bio": bio,
            "level": level,
            "games_count": games_count,
            "total_playtime": total_playtime,
            "top_games": top_games,
            "recently_played": recently_played,
            "is_public": is_public
        }


        return {
            "player": player,
            "bio": bio,
            "level": level,
            "games_count": games_count,
            "total_playtime": total_playtime,
            "recently_played": recently_played,
            "is_public": is_public
        }

    @commands.command(name="osu", help="Chouf chy profile f osu!.")
    async def osu(self, ctx, username: str):
        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))
        
        url = f"https://osu.ppy.sh/users/{urllib.parse.quote(username)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        await wait.edit(embed=discord.Embed(description=f"Mal9itch had l user f osu!: `{username}`", color=0x000000))
                        return
                    if resp.status != 200:
                        raise Exception(f"osu! website returned status {resp.status}")
                    html_data = await resp.text()

            match = re.search(r'data-initial(?:-data|\s+data)=["\']([^"\']+)["\']', html_data)
            if not match:
                await wait.edit(embed=discord.Embed(description="Mal9it ta data f page dyal had l user.", color=0x000000))
                return

            import json
            decoded_json = html.unescape(match.group(1))
            data = json.loads(decoded_json)

            user = data.get("user")
            if not user:
                await wait.edit(embed=discord.Embed(description="Mal9itch user info.", color=0x000000))
                return

            user_id = user.get("id")
            display_name = user.get("username", username)
            avatar_url = user.get("avatar_url")
            cover_url = user.get("cover_url")
            country_name = user.get("country", {}).get("name", "Unknown")
            country_code = user.get("country_code", "")
            flag_emoji = ""
            if country_code and len(country_code) == 2:
                flag_emoji = "".join(chr(ord(c) + 127397) for c in country_code.upper())
                
            join_date_str = user.get("join_date", "")
            
            join_date = "Unknown"
            if join_date_str:
                try:
                    join_date = join_date_str.split("T")[0]
                except Exception:
                    pass

            stats = user.get("statistics")
            global_rank = "N/A"
            country_rank = "N/A"
            pp = "N/A"
            accuracy = "N/A"
            play_count = "N/A"
            play_time = "N/A"
            level = "N/A"
            grades = "N/A"

            if stats:
                global_rank = f"#{stats.get('global_rank')}" if stats.get("global_rank") else "Unranked"
                country_rank = f"#{stats.get('country_rank')}" if stats.get("country_rank") else "Unranked"
                pp = f"{stats.get('pp'):,.2f}pp" if stats.get("pp") is not None else "0pp"
                accuracy = f"{stats.get('hit_accuracy'):.2f}%" if stats.get("hit_accuracy") is not None else "0.00%"
                play_count = f"{stats.get('play_count'):,}" if stats.get("play_count") is not None else "0"
                
                pt_seconds = stats.get("play_time")
                if pt_seconds:
                    play_time = f"{pt_seconds // 3600:,}h"
                else:
                    play_time = "0h"

                lvl = stats.get("level", {})
                if lvl:
                    level = f"{lvl.get('current')} ({lvl.get('progress')}% progress)"

                g_counts = stats.get("grade_counts", {})
                if g_counts:
                    grades = (
                        f"**SS** {g_counts.get('ss', 0):,} | **SSH** {g_counts.get('ssh', 0):,}\n"
                        f"**S** {g_counts.get('s', 0):,} | **SH** {g_counts.get('sh', 0):,}\n"
                        f"**A** {g_counts.get('a', 0):,}"
                    )

            profile_url = f"https://osu.ppy.sh/users/{user_id}"
            title_text = f"osu! Profile: {display_name} {flag_emoji}".strip()
            embed = discord.Embed(
                title=title_text,
                url=profile_url,
                color=0x000000
            )
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            if cover_url:
                embed.set_image(url=cover_url)

            embed.add_field(name="Global Rank", value=global_rank, inline=True)
            embed.add_field(name="Country Rank", value=f"{country_rank} ({country_name})", inline=True)
            embed.add_field(name="Performance", value=pp, inline=True)
            embed.add_field(name="Accuracy", value=accuracy, inline=True)
            embed.add_field(name="Play Count", value=play_count, inline=True)
            embed.add_field(name="Play Time", value=play_time, inline=True)
            embed.add_field(name="Level", value=level, inline=True)
            embed.add_field(name="Joined Date", value=join_date, inline=True)
            if grades:
                embed.add_field(name="Grades", value=grades, inline=False)

            await wait.edit(embed=embed)

        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))
        finally:
            import gc
            if 'html_data' in locals():
                del html_data
            if 'data' in locals():
                del data
            gc.collect()


    @commands.command(name="rocketleague", aliases=["rl", "rlstats"], help="Chouf stats ta3 chy wa7d f Rocket League.")
    async def rocketleague(self, ctx, *args):
        if not args:
            await ctx.send(embed=discord.Embed(
                description=f"3tini username dyal Rocket League.\n**Example:** `{ctx.prefix}rl epic ApparentlyJack` wla `{ctx.prefix}rl ApparentlyJack`\n**Platforms:** `epic`, `steam`, `psn`, `xbl`, `switch`",
                color=0x000000
            ))
            return

        platforms = {"epic", "steam", "psn", "xbl", "xbox", "switch", "playstation", "nintendo"}
        first_arg = args[0].lower()
        if first_arg in platforms and len(args) > 1:
            platform = first_arg
            if platform == "xbox":
                platform = "xbl"
            elif platform == "playstation":
                platform = "psn"
            elif platform == "nintendo":
                platform = "switch"
            username = " ".join(args[1:])
        else:
            platform = "epic"
            username = " ".join(args)

        wait = await ctx.send(embed=discord.Embed(description="Sber 3lia...", color=0x000000))

        try:
            status, data = await asyncio.to_thread(_fetch_rl_sync, platform, username)

            if status == 404 or not data:
                await wait.edit(embed=discord.Embed(
                    description=f"Mal9itch had l user f Rocket League: `{username}` (Platform: `{platform}`)",
                    color=0x000000
                ))
                return

            if status != 200:
                await wait.edit(embed=discord.Embed(
                    description=f"Tracker Network returned status `{status}`. Jarreb mn be3d.",
                    color=0x000000
                ))
                return

            profile_data = data.get("data", {})
            platform_info = profile_data.get("platformInfo", {})
            user_handle = platform_info.get("platformUserHandle", username)
            avatar_url = platform_info.get("avatarUrl")
            platform_slug = platform_info.get("platformSlug", platform).lower()

            platform_names = {
                "epic": "Epic Games",
                "steam": "Steam",
                "psn": "PlayStation Network",
                "xbl": "Xbox Live",
                "switch": "Nintendo Switch"
            }
            platform_display = platform_names.get(platform_slug, platform_slug.capitalize())
            profile_url = f"https://rocketleague.tracker.network/rocket-league/profile/{platform_slug}/{urllib.parse.quote(user_handle)}/overview"

            segments = profile_data.get("segments", [])
            overview_stats = {}
            playlists = {}

            for seg in segments:
                stype = seg.get("type")
                if stype == "overview":
                    for k, v in seg.get("stats", {}).items():
                        overview_stats[k] = v.get("displayValue", "N/A")
                elif stype == "playlist":
                    pname = seg.get("metadata", {}).get("name", "Unknown")
                    stats = seg.get("stats", {})
                    tier_info = stats.get("tier", {}).get("metadata", {})
                    div_info = stats.get("division", {}).get("metadata", {})

                    playlists[pname] = {
                        "tier": tier_info.get("name", "Unranked"),
                        "division": div_info.get("name", ""),
                        "mmr": stats.get("rating", {}).get("displayValue", "N/A"),
                        "matches": stats.get("matchesPlayed", {}).get("displayValue", "0"),
                        "streak": stats.get("winStreak", {}).get("displayValue", "0"),
                        "peak": stats.get("peakRating", {}).get("displayValue", "N/A"),
                        "icon": tier_info.get("iconUrl")
                    }

            primary_icon = (
                playlists.get("Ranked Doubles 2v2", {}).get("icon")
                or playlists.get("Ranked Standard 3v3", {}).get("icon")
                or playlists.get("Ranked Duel 1v1", {}).get("icon")
                or "https://trackercdn.com/cdn/tracker.gg/rocket-league/ranks/s4-0.png"
            )

            # Format helper
            def format_mode(key):
                p = playlists.get(key)
                if not p:
                    return "`Unranked` (0 MMR)"
                div_str = f" • {p['division']}" if p.get('division') else ""
                streak_val = p.get('streak', '0')
                streak_str = f" • Streak: `{streak_val}`" if streak_val != "0" else ""
                return f"**{p['tier']}**{div_str}\n`{p['mmr']} MMR` ({p['matches']} matches{streak_str})"

            # Page 1: Overview & Main Competitive
            embed_p1 = discord.Embed(
                title=f"Rocket League Stats: {user_handle}",
                url=profile_url,
                color=0x000000
            )
            if avatar_url:
                embed_p1.set_thumbnail(url=avatar_url)
            elif primary_icon:
                embed_p1.set_thumbnail(url=primary_icon)

            embed_p1.set_author(name=f"{platform_display} Profile", icon_url=primary_icon)

            wins = overview_stats.get("wins", "N/A")
            goals = overview_stats.get("goals", "N/A")
            saves = overview_stats.get("saves", "N/A")
            assists = overview_stats.get("assists", "N/A")
            mvps = overview_stats.get("mVPs", "N/A")
            accuracy = f"{overview_stats.get('goalShotRatio')}%" if overview_stats.get("goalShotRatio") else "N/A"
            trn_score = overview_stats.get("score", "N/A")

            overview_val = (
                f"🏆 **Wins:** `{wins}` | 🎯 **Goals:** `{goals}`\n"
                f"🧤 **Saves:** `{saves}` | 🤝 **Assists:** `{assists}`\n"
                f"⭐ **MVPs:** `{mvps}` | 🎯 **Accuracy:** `{accuracy}`\n"
                f"📊 **TRN Score:** `{trn_score}`"
            )
            embed_p1.add_field(name="📈 Lifetime Overview", value=overview_val, inline=False)
            embed_p1.add_field(name="⚔️ Ranked 1v1 Duel", value=format_mode("Ranked Duel 1v1"), inline=True)
            embed_p1.add_field(name="👥 Ranked 2v2 Doubles", value=format_mode("Ranked Doubles 2v2"), inline=True)
            embed_p1.add_field(name="🛡️ Ranked 3v3 Standard", value=format_mode("Ranked Standard 3v3"), inline=True)

            tourn = playlists.get("Tournament Matches")
            tourn_text = f"**{tourn['tier']}**\n`{tourn['mmr']} MMR`" if tourn else "`Unranked`"
            embed_p1.add_field(name="🏅 Tournaments", value=tourn_text, inline=True)

            casual = playlists.get("Casual")
            casual_text = f"`{casual['mmr']} MMR`" if casual else "`N/A`"
            embed_p1.add_field(name="🎮 Casual MMR", value=casual_text, inline=True)

            embed_p1.set_footer(text="Page 1/2 • Use buttons below to switch views")

            # Page 2: Extra Modes
            embed_p2 = discord.Embed(
                title=f"Rocket League Extra Modes: {user_handle}",
                url=profile_url,
                color=0x000000
            )
            if avatar_url:
                embed_p2.set_thumbnail(url=avatar_url)
            elif primary_icon:
                embed_p2.set_thumbnail(url=primary_icon)

            embed_p2.set_author(name=f"{platform_display} Profile", icon_url=primary_icon)
            embed_p2.add_field(name="🏀 Hoops", value=format_mode("Hoops"), inline=True)
            embed_p2.add_field(name="⚡ Rumble", value=format_mode("Rumble"), inline=True)
            embed_p2.add_field(name="💥 Dropshot", value=format_mode("Dropshot"), inline=True)
            embed_p2.add_field(name="🏒 Snowday", value=format_mode("Snowday"), inline=True)
            embed_p2.add_field(name="🚙 Ranked 4v4 Quads", value=format_mode("Ranked 4v4 Quads"), inline=True)

            embed_p2.set_footer(text="Page 2/2 • Use buttons below to switch views")

            view = RocketLeagueView(author_id=ctx.author.id, embed_p1=embed_p1, embed_p2=embed_p2, profile_url=profile_url)
            await wait.edit(embed=embed_p1, view=view)

        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))
        finally:
            import gc
            if 'data' in locals():
                del data
            gc.collect()


    @commands.command(name="shortenurl", aliases=["shorten", "shorturl", "tinyurl", "short"], help="9esser chy link/URL twil.")
    async def shortenurl(self, ctx, url: str = None):
        if not url:
            await ctx.send(embed=discord.Embed(
                description=f"3tini link li bghiti t9esser.\n**Example:** `{ctx.prefix}shortenurl https://example.com/very/long/url`",
                color=0x000000
            ))
            return

        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        wait = await ctx.send(embed=discord.Embed(description="Kan9esser f link...", color=0x000000))
        encoded_url = urllib.parse.quote(clean_url, safe=":/?#[]@!$&'()*+,;=")
        api_url = f"https://tinyurl.com/api-create.php?url={encoded_url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        try:
            async with ReusableSession(self.bot.session) as session:
                async with session.get(api_url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        short_url = (await resp.text()).strip()
                        if short_url.startswith("http"):
                            embed = discord.Embed(
                                title="🔗 Link T9esser",
                                description=f"• **Original:** {clean_url}\n• **Shortened:** {short_url}",
                                color=0x000000
                            )
                            embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Open Link", url=short_url, style=discord.ButtonStyle.link))
                            await wait.edit(embed=embed, view=view)
                            return

            await wait.edit(embed=discord.Embed(description="❌ Ma9ditch n9esser had l link. T2ked mn URL.", color=0x000000))
        except Exception as e:
            await wait.edit(embed=discord.Embed(description=f"Tra chy mochkil: `{e}`", color=0x000000))


async def setup(bot):
    await bot.add_cog(GlobUtil(bot))