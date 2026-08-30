import asyncio
import base64
import os
import re
import time
from collections import deque

import aiohttp
import discord
import yt_dlp
from discord.ext import commands
from spotify_scraper import AsyncSpotifyClient, NotFoundError, SpotifyScraperError

YTDL_OPTS = {
    "format": "bestaudio/best",
    # Only matters for a URL that's BOTH a video and a playlist
    # (watch?v=...&list=...) - loads just that video. A bare playlist
    # URL (playlist?list=...) always extracts the whole playlist
    # regardless of this setting.
    "noplaylist": True,
    "default_search": "ytsearch",
    "quiet": True,
    "no_warnings": True,
    # "in_playlist" is the fix for slow-starting big playlists: it stops
    # yt-dlp from resolving every entry's actual playable stream URL up
    # front (which for a 100-track playlist meant 100 sequential
    # extractions before track #1 could even start). Entries inside a
    # playlist/search result now come back "flat" - title/id/duration
    # only, no stream URL - and each one gets fully resolved lazily,
    # right before its own turn to play (see Music._resolve_track).
    # A single direct video URL (not a playlist/search) is unaffected -
    # yt-dlp only applies flat mode to nested playlist entries, so that
    # case is still fully resolved immediately, as before.
    "extract_flat": "in_playlist",
    "source_address": "0.0.0.0",
    # Let a single bad entry (age-restricted/private/deleted) in a
    # playlist get skipped instead of aborting extraction of the
    # whole playlist.
    "ignoreerrors": True,
}

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean_ytdl_message(msg: str) -> str:
    """Strip ANSI color codes and yt-dlp's 'ERROR:' prefix, and cap length,
    so error text is safe/readable to paste into a Discord message."""
    msg = _ANSI_ESCAPE_RE.sub("", str(msg)).strip()
    if msg.upper().startswith("ERROR:"):
        msg = msg[len("ERROR:"):].strip()
    if len(msg) > 300:
        msg = msg[:300].rstrip() + "..."
    return msg


def _looks_like_playlist_query(query: str) -> bool:
    """Heuristic used to decide whether a query is worth a background
    "fetch the rest of the playlist" pass after queueing just its first
    track. False negatives just mean we treat something as a single
    track (harmless); false positives just mean one extra background
    listing call that turns up nothing extra to queue (harmless)."""
    q = query.lower()
    return ("list=" in q) or ("/playlist" in q) or ("/sets/" in q) or ("/album/" in q)


class _YTDLLogger:
    """Captures yt-dlp's error text instead of printing it, so we can still
    surface a specific, clean reason to the user even though ignoreerrors
    lets extraction continue past a bad entry."""

    def __init__(self):
        self.last_error: str | None = None

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.last_error = _clean_ytdl_message(msg)


# Matches open.spotify.com links (including regional "/intl-en/" links and
# the "?si=..." share suffix) as well as raw spotify:track:ID style URIs.
SPOTIFY_URL_RE = re.compile(
    r"(?:open\.spotify\.com/(?:intl-[a-zA-Z-]+/)?|spotify:)(track|album|playlist)[/:]([A-Za-z0-9]+)"
)


class SpotifyClient:
    """Minimal wrapper around Spotify's Web API using the Client Credentials
    flow (app-only auth - no user login needed). Spotify's API only ever
    gives back metadata; it never hands out playable audio, so this is used
    purely to look up track names/artists/durations for single tracks and
    albums, which are then matched against YouTube. (Playlists are handled
    separately - see Music.spotify_scraper below.)"""

    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE = "https://api.spotify.com/v1"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._session: aiohttp.ClientSession | None = None
        self._token_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get_token(self, force_refresh: bool = False) -> str:
        async with self._token_lock:
            if not force_refresh and self._token and time.time() < self._token_expires_at - 30:
                return self._token
            session = await self._get_session()
            auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers = {"Authorization": f"Basic {auth}"}
            data = {"grant_type": "client_credentials"}
            async with session.post(self.TOKEN_URL, headers=headers, data=data) as resp:
                if resp.status != 200:
                    text = (await resp.text())[:200]
                    raise RuntimeError(f"Spotify auth failed ({resp.status}): {text}")
                payload = await resp.json()
            self._token = payload["access_token"]
            self._token_expires_at = time.time() + payload.get("expires_in", 3600)
            return self._token

    async def _get(self, path: str, params: dict | None = None) -> dict:
        token = await self._get_token()
        session = await self._get_session()
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(f"{self.API_BASE}{path}", headers=headers, params=params) as resp:
            if resp.status == 401:
                # Token expired/revoked mid-flight - refresh once and retry.
                token = await self._get_token(force_refresh=True)
                headers = {"Authorization": f"Bearer {token}"}
                async with session.get(f"{self.API_BASE}{path}", headers=headers, params=params) as retry:
                    retry.raise_for_status()
                    return await retry.json()
            resp.raise_for_status()
            return await resp.json()

    @staticmethod
    def _track_to_info(track: dict) -> dict | None:
        if not track or track.get("is_local"):
            return None
        artists = ", ".join(a.get("name", "") for a in track.get("artists", []) if a.get("name"))
        title = track.get("name")
        if not title:
            return None
        return {"title": title, "artist": artists, "duration_ms": track.get("duration_ms")}

    async def get_track(self, track_id: str) -> dict | None:
        data = await self._get(f"/tracks/{track_id}")
        return self._track_to_info(data)

    async def get_album_tracks(self, album_id: str) -> list[dict]:
        tracks: list[dict] = []
        params = {"limit": 50, "offset": 0}
        while True:
            page = await self._get(f"/albums/{album_id}/tracks", params=params)
            for item in page.get("items", []):
                info = self._track_to_info(item)
                if info:
                    tracks.append(info)
            if not page.get("next"):
                break
            params["offset"] += params["limit"]
        return tracks

    async def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        """NOTE: as of Spotify's Feb 2026 API changes, Client Credentials
        auth (no logged-in user) can only ever get this for a playlist it
        owns - which, for an app-only bot, is never. Kept for playlists
        the app itself might own in future; play() now sources playlist
        tracks from SpotifyScraper instead (see below)."""
        tracks: list[dict] = []
        params = {
            "limit": 100,
            "offset": 0,
            # Feb 2026 API change renamed the per-entry key: track -> item
            # (a playlist item can now be a track, episode, etc).
            "fields": "items(item(name,artists(name),duration_ms,is_local)),next",
        }
        while True:
            try:
                # /tracks is the old path; blocked outright for
                # Development Mode apps now. /items is the current one.
                page = await self._get(f"/playlists/{playlist_id}/items", params=params)
            except aiohttp.ClientResponseError as e:
                if e.status == 403:
                    # Playlist contents are only returned to the owner/a
                    # collaborator; a playlist we don't own either 403s
                    # outright or comes back metadata-only (caught below).
                    # Either way: no tracks, not an error.
                    break
                raise

            if "items" not in page:
                break

            for item in page.get("items", []):
                info = self._track_to_info(item.get("item"))
                if info:
                    tracks.append(info)
            if not page.get("next"):
                break
            params["offset"] += params["limit"]
        return tracks


class Track:
    """
    A queued track can be created in two states:
      - Resolved: `url` is already a playable stream URL (used for a
        direct single-video link, which yt-dlp fully extracts up front
        anyway since flat mode only affects nested playlist entries).
      - Unresolved: `url` is None, and either `webpage_url` (a YouTube
        page to fully extract later) or `resolve_query` (a search string,
        used for Spotify-sourced tracks) is set instead. Resolution
        happens lazily, right before the track's turn to play - see
        Music._resolve_track.
    """

    def __init__(
        self,
        requester: discord.Member,
        *,
        title: str = "Unknown title",
        url: str | None = None,
        webpage_url: str | None = None,
        duration: float | None = None,
        resolve_query: str | None = None,
        target_duration: float | None = None,
    ):
        self.requester = requester
        self.title = title or "Unknown title"
        self.url = url
        self.webpage_url = webpage_url
        self.duration = duration
        self.resolve_query = resolve_query
        self.target_duration = target_duration
        self.resolve_error: str | None = None

    @classmethod
    def from_entry(cls, entry: dict, requester: discord.Member) -> "Track":
        """Builds a Track from a yt-dlp result entry, which may be either
        a fully-resolved single video (has 'formats') or a flat playlist/
        search entry (no 'formats' - title/id/duration only)."""
        resolved = bool(entry.get("formats"))
        title = entry.get("title") or "Unknown title"
        duration = entry.get("duration")
        if resolved:
            return cls(
                requester,
                title=title,
                url=entry.get("url"),
                webpage_url=entry.get("webpage_url", entry.get("original_url", "")),
                duration=duration,
            )

        # In flat mode, entry['url'] is normally a page link, not a
        # stream - exactly what we want to resolve from later. But some
        # yt-dlp versions/extractors hand back a bare video ID instead of
        # a full URL for flat entries, which then fails to resolve since
        # it gets treated as a search query instead of a direct link.
        # Reconstruct a proper watch URL from the id in that case.
        webpage_url = entry.get("webpage_url")
        if not webpage_url:
            raw = entry.get("url")
            video_id = entry.get("id")
            if raw and raw.startswith(("http://", "https://")):
                webpage_url = raw
            elif video_id:
                webpage_url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                webpage_url = raw
        return cls(requester, title=title, webpage_url=webpage_url, duration=duration)

    @classmethod
    def from_spotify(cls, title: str, artist: str, duration_ms: int | None, requester: discord.Member) -> "Track":
        display_title = f"{artist} - {title}" if artist else title
        query = f"ytsearch5:{artist} - {title} audio".strip()
        target_duration = (duration_ms / 1000) if duration_ms else None
        return cls(
            requester,
            title=display_title,
            resolve_query=query,
            duration=target_duration,
            target_duration=target_duration,
        )

    def duration_str(self) -> str:
        if not self.duration:
            return "Live/Unknown"
        total = int(self.duration)
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


class GuildMusicState:
    def __init__(self, bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.queue: deque[Track] = deque()
        self.voice_client: discord.VoiceClient | None = None
        self.current: Track | None = None
        self.volume = 0.5
        self.loop_current = False
        self.text_channel: discord.TextChannel | None = None
        self.play_next_event = asyncio.Event()
        self.player_task = None
        self.status_refresh_task: asyncio.Task | None = None
        self.status_message: discord.Message | None = None
        self.started_at: float | None = None
        self.elapsed_before_pause = 0.0
        # Loops the single current track forever. Mutually exclusive with
        # loop_queue (see Music.toggle_loop / toggle_queue_loop) - only
        # one "loop mode" is active at a time to avoid confusing combos.
        self.loop_queue = False
        # Serializes status-message repost/edit operations so two commands
        # firing close together (e.g. two quick /play calls) can't both
        # delete+repost at once and leave a duplicate message behind.
        self.status_lock = asyncio.Lock()

    def start_player_loop(self):
        if self.player_task is None or self.player_task.done():
            self.player_task = self.bot.loop.create_task(self._player_loop())

    def get_elapsed_seconds(self) -> float:
        if not self.current:
            return 0.0
        if self.started_at is not None:
            return self.elapsed_before_pause + (time.monotonic() - self.started_at)
        return self.elapsed_before_pause

    def start_status_refresh_loop(self):
        if self.status_refresh_task is not None and not self.status_refresh_task.done():
            return

        async def _loop():
            while self.current and self.voice_client and self.voice_client.is_connected():
                await asyncio.sleep(5)
                music = self.bot.get_cog("Music")
                if music:
                    await music.refresh_status_for_guild(self.guild_id)

        self.status_refresh_task = self.bot.loop.create_task(_loop())

    def cancel_status_refresh_loop(self):
        # NOTE: only ever call this from the event loop thread (i.e. from
        # inside _player_loop or a command coroutine), never from the
        # discord.py audio-player thread (the `after=` callback).
        if self.status_refresh_task is not None:
            self.status_refresh_task.cancel()
            self.status_refresh_task = None

    async def _player_loop(self):
        while True:
            self.play_next_event.clear()
            # Safe to do here: we're on the event loop thread, unlike the
            # `after_playing` callback below which runs on discord.py's
            # separate audio-player thread.
            self.cancel_status_refresh_loop()

            if not self.loop_current or self.current is None:
                # Queue loop: the track that just finished goes to the
                # back of the queue instead of being discarded, so the
                # whole queue repeats once it's worked through. Skipped
                # when current is None (nothing actually just finished -
                # e.g. fresh start, or the previous track failed to
                # resolve and was already dropped).
                if self.loop_queue and self.current is not None:
                    self.queue.append(self.current)

                if not self.queue:
                    # Nothing playing and nothing queued: reflect that in
                    # state so callers (like /play) can tell we're idle,
                    # and so the "now playing" message clears itself.
                    self.current = None
                    self.started_at = None
                    self.elapsed_before_pause = 0.0
                    music = self.bot.get_cog("Music")
                    if music:
                        await music.refresh_status_for_guild(self.guild_id)
                    try:
                        await asyncio.wait_for(self.play_next_event.wait(), timeout=180)
                        continue
                    except asyncio.TimeoutError:
                        if self.voice_client and self.voice_client.is_connected():
                            await self.voice_client.disconnect()
                        if self.status_message:
                            try:
                                await self.status_message.delete()
                            except discord.HTTPException:
                                pass
                            self.status_message = None
                        return
                self.current = self.queue.popleft()
                self.started_at = time.monotonic()
                self.elapsed_before_pause = 0.0

                # Lazy resolution: this track was queued as a lightweight
                # placeholder (flat YouTube entry, or a Spotify metadata
                # match with no YouTube match yet). Resolve it now - right
                # before ITS turn - instead of every track in a playlist
                # having been resolved upfront, which is what made big
                # playlists take forever to start.
                if self.current.url is None:
                    music = self.bot.get_cog("Music")
                    resolved_ok = await music._resolve_track(self.current) if music else False
                    if not resolved_ok:
                        if self.text_channel:
                            reason = self.current.resolve_error or "couldn't be loaded"
                            try:
                                await self.text_channel.send(f"⚠️ Skipping **{self.current.title}** — {reason}")
                            except discord.HTTPException:
                                pass
                        self.current = None
                        continue  # try the next queued track right away, no waiting

            if not self.voice_client or not self.voice_client.is_connected():
                return

            try:
                source = discord.FFmpegPCMAudio(
                    self.current.url,
                    before_options=FFMPEG_BEFORE_OPTS,
                    options=FFMPEG_OPTS,
                )
                source = discord.PCMVolumeTransformer(source, volume=self.volume)

                def after_playing(error, track=self.current):
                    if error:
                        print(f"[music] playback error: {error}")
                    # Only thread-safe asyncio calls belong here - this runs
                    # on discord.py's audio-player thread, not the event loop.
                    self.bot.loop.call_soon_threadsafe(self.play_next_event.set)

                self.voice_client.play(source, after=after_playing)
            except Exception as e:
                # Don't let a single bad track (expired URL, ffmpeg failure,
                # "already playing" race, etc.) permanently kill the queue.
                print(f"[music] failed to start playback for '{self.current.title}': {e}")
                self.current = None
                continue

            self.start_status_refresh_loop()
            music = self.bot.get_cog("Music")
            if music:
                await music.refresh_status_for_guild(self.guild_id)
            await self.play_next_event.wait()


class QueueSelect(discord.ui.Select):
    def __init__(self, music: "Music", guild_id: int):
        self.music = music
        self.guild_id = guild_id
        state = music.get_state(guild_id)
        options = []
        queue_items = list(state.queue)[:25]
        is_empty = not queue_items
        if is_empty:
            options.append(discord.SelectOption(label="Queue is empty", value="empty", description="No tracks queued right now"))
        else:
            for index, track in enumerate(queue_items, start=1):
                label = f"{index}. {track.title}"
                if len(label) > 100:
                    label = label[:97] + "..."
                options.append(discord.SelectOption(label=label, value=str(index), description=track.duration_str()))
        # Keep a fixed placeholder regardless of queue contents so the row
        # doesn't visually change shape, and disable it when there's
        # nothing to pick so it doesn't look like a live, empty control.
        super().__init__(placeholder="Upcoming queue", options=options, min_values=0, max_values=1, disabled=is_empty)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0] if self.values else None
        if not value or value == "empty":
            await interaction.response.defer()
            return

        state = self.music.get_state(self.guild_id)

        try:
            index = int(value) - 1
        except ValueError:
            await interaction.response.defer()
            return

        queue_list = list(state.queue)
        if index < 0 or index >= len(queue_list):
            # Queue changed between the menu being built and the click -
            # stale selection, just ignore it rather than jump to the
            # wrong track.
            await interaction.response.defer()
            return

        # Pull the selected track out of wherever it sits, WITHOUT
        # reordering anything else - the rest of the queue keeps its
        # existing relative order.
        selected = queue_list.pop(index)
        state.queue = deque(queue_list)
        # Put it at the very front so it's the next (and only the next)
        # thing the player loop picks up.
        state.queue.appendleft(selected)

        await interaction.response.defer()

        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            # Dropping the current track: stopping playback fires the
            # `after_playing` callback, which wakes the player loop, which
            # then pops our freshly-front-loaded selection as the new
            # current track.
            state.voice_client.stop()
        else:
            state.start_player_loop()
            state.play_next_event.set()


class NowPlayingView(discord.ui.View):
    def __init__(self, music: "Music", guild_id: int):
        super().__init__(timeout=None)
        self.music = music
        self.guild_id = guild_id
        self.add_item(QueueSelect(music, guild_id))

        # Reflect actual playback state on the pause/resume button instead
        # of a static label, so it always shows the action that will
        # happen next, whether toggled via this button or /pause /resume.
        state = music.get_state(guild_id)
        is_paused = bool(state.voice_client and state.voice_client.is_paused())
        if is_paused:
            self.pause_button.label = " Play"
            self.pause_button.emoji = "▶️"
        else:
            self.pause_button.label = " Pause"
            self.pause_button.emoji = "⏸️"

        # Loop button reflects and toggles single-track loop. Highlighted
        # (primary/green) when active, same pattern as the pause button.
        if state.loop_current:
            self.loop_button.label = " Loop: On"
            self.loop_button.style = discord.ButtonStyle.success
        else:
            self.loop_button.label = " Loop: Off"
            self.loop_button.style = discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        state = self.music.get_state(self.guild_id)
        if (
            interaction.user.voice
            and state.voice_client
            and interaction.user.voice.channel
            and interaction.user.voice.channel.id == state.voice_client.channel.id
        ):
            return True
        await interaction.response.send_message("Must be in the same voice channel to control music.", ephemeral=True)
        return False

    @discord.ui.button(label=" Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.music.skip_track(self.guild_id)

    @discord.ui.button(label=" Pause", style=discord.ButtonStyle.primary, emoji="⏸️")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.music.toggle_pause(self.guild_id)

    @discord.ui.button(label=" Loop: Off", style=discord.ButtonStyle.secondary, emoji="🔂")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.music.toggle_loop(self.guild_id)

    @discord.ui.button(label=" Quit", style=discord.ButtonStyle.danger, emoji="🛑")
    async def quit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.music.stop_music(self.guild_id)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}

        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        self.spotify = SpotifyClient(client_id, client_secret) if client_id and client_secret else None
        # No app credentials needed - reads Spotify's public web-player
        # endpoints directly instead of the official Web API. Used for
        # playlists (see play()), since Client Credentials auth can't
        # read a playlist's contents unless the app itself owns it.
        self.spotify_scraper = AsyncSpotifyClient()

    async def cog_unload(self):
        if self.spotify:
            await self.spotify.close()
        await self.spotify_scraper.aclose()

    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState(self.bot, guild_id)
        return self.states[guild_id]

    async def ensure_voice(self, ctx: commands.Context) -> GuildMusicState | None:
        state = self.get_state(ctx.guild.id)

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("Khassk tkoun f voice channel bach ndir hadchi.")
            return None

        if state.voice_client is None or not state.voice_client.is_connected():
            state.voice_client = await ctx.author.voice.channel.connect()
        elif state.voice_client.channel.id != ctx.author.voice.channel.id:
            await state.voice_client.move_to(ctx.author.voice.channel)

        state.text_channel = ctx.channel
        return state

    async def _extract_ytdl(
        self, query: str, *, flat: bool = True, playlist_items: str | None = None
    ) -> tuple[dict | None, "_YTDLLogger"]:
        """Runs yt-dlp's extract_info off the event loop thread. Returns
        (data, logger) - data is None on total failure, in which case
        logger.last_error usually has a clean reason why.

        flat=True (the default) is for the fast initial listing pass -
        cheap, no playable stream URLs. flat=False is for actually
        resolving a specific track to a playable stream right before it
        plays, and must NOT inherit flat mode - it needs the full
        extraction to get a usable 'url'.

        playlist_items lets a listing pass ask yt-dlp for only specific
        entries (e.g. "1") instead of the whole playlist - used to peek
        at just the first track quickly, see play()."""
        loop = asyncio.get_event_loop()
        logger = _YTDLLogger()
        opts = dict(YTDL_OPTS)
        opts["extract_flat"] = "in_playlist" if flat else False
        opts["logger"] = logger
        if playlist_items:
            opts["playlist_items"] = playlist_items

        def _run():
            with yt_dlp.YoutubeDL(opts) as instance:
                return instance.extract_info(query, download=False)

        data = await loop.run_in_executor(None, _run)
        return data, logger

    async def search(self, query: str) -> tuple[list[dict], int]:
        """
        Resolves a query - a search term, a single video URL, or a
        playlist URL.

        Returns (entries, skipped):
        - Single video / search term: entries has 0 or 1 items.
        - Playlist: entries has every item that came back (each one still
          "flat" - not yet resolved to a playable stream, see Track); any
          that errored outright during listing (rare - most bad entries
          only surface once we try to fully resolve them later) are
          counted in `skipped` instead of aborting the whole thing.
        Raises on total failure (e.g. bad search / totally invalid URL),
        with a clean message pulled from yt-dlp's own error output.
        """
        data, logger = await self._extract_ytdl(query)

        if data is None:
            raise ValueError(logger.last_error or "No results found.")

        if "entries" in data:
            raw_entries = list(data["entries"])
            entries = [e for e in raw_entries if e]
            skipped = len(raw_entries) - len(entries)
            return entries, skipped

        return [data], 0

    async def _resolve_track(self, track: Track) -> bool:
        """
        Fills in `track.url` (a playable stream) for a track that was
        queued as a lightweight placeholder. Tries, in order:
          - `track.webpage_url` (a flat YouTube playlist/search entry)
          - `track.resolve_query` (a Spotify track's "artist - title"
            search string) - picks whichever of the top few results has
            the closest duration to Spotify's, to avoid matching a wrong
            cover/remix/reaction video.
        Returns True on success; on failure, sets `track.resolve_error`
        to a clean, user-facing reason and returns False.
        """
        if track.url:
            return True

        if not track.webpage_url and not track.resolve_query:
            track.resolve_error = "No source to resolve."
            return False

        try:
            data, logger = await self._extract_ytdl(track.webpage_url or track.resolve_query, flat=False)
        except Exception as e:
            track.resolve_error = _clean_ytdl_message(e)
            return False

        if data and "entries" in data:
            candidates = [e for e in data["entries"] if e]
            if not candidates:
                track.resolve_error = logger.last_error or "No results found."
                return False
            if track.target_duration:
                candidates.sort(key=lambda e: abs((e.get("duration") or 0) - track.target_duration))
            data = candidates[0]

        if not data:
            track.resolve_error = logger.last_error or "No results found."
            return False

        stream_url = data.get("url")
        if not stream_url:
            track.resolve_error = "No playable stream found."
            return False

        track.url = stream_url
        if not track.webpage_url:
            track.webpage_url = data.get("webpage_url", data.get("original_url", ""))
        if not track.duration:
            track.duration = data.get("duration")
        return True

    async def _fill_playlist_remainder(self, ctx: commands.Context, query: str, cap: int):
        """Runs in the background after /play on a playlist link: fetches
        the FULL flat listing and appends everything past the first track
        (already queued - and likely already playing - by the time this
        finishes) to the queue. This is what lets track #1 start right
        away instead of waiting for the whole playlist to be listed."""
        state = self.get_state(ctx.guild.id)
        try:
            data, logger = await self._extract_ytdl(query)
        except Exception as e:
            try:
                await ctx.channel.send(f"⚠️ Couldn't load the rest of that playlist: `{_clean_ytdl_message(e)}`")
            except discord.HTTPException:
                pass
            return

        try:
            if not data or "entries" not in data:
                return

            entries = [e for e in data["entries"] if e]
            if not entries:
                return

            truncated = len(entries) > cap
            entries = entries[:cap]
            # Index 0 is the same track /play already queued - skip it.
            remainder = entries[1:]
            if not remainder:
                return

            added = [Track.from_entry(e, ctx.author) for e in remainder]
            state.queue.extend(added)
            await self.refresh_status_for_guild(ctx.guild.id)

            msg = f"➕ Finished loading the playlist — added **{len(added)}** more track{'s' if len(added) != 1 else ''}."
            if truncated:
                msg += f" (capped at {cap} total)"
            await ctx.channel.send(msg)
        except Exception as e:
            print(f"[music] error filling playlist remainder: {e}")

    async def _queue_and_announce(
        self,
        ctx: commands.Context,
        state: GuildMusicState,
        tracks: list[Track],
        *,
        skipped: int = 0,
        truncated: bool = False,
        cap: int | None = None,
        multi_label: str = "tracks",
        skip_reason: str = "couldn't be loaded",
        extra_note: str | None = None,
    ):
        """Shared tail end of /play: queues already-built Tracks, wakes
        the player loop if it was idle, and sends the right confirmation
        message for either a single track or a batch (playlist)."""
        already_active = state.current is not None
        added_tracks = tracks
        state.queue.extend(added_tracks)

        state.start_player_loop()
        if not already_active:
            # Only nudge the loop when it's genuinely idle (waiting on
            # this event for a new track). If a track is already playing,
            # the loop is instead waiting for THAT track to finish, and
            # setting the event here would make it think the current song
            # ended and jump straight to voice_client.play() while the
            # old one is still playing - which raises "Already playing
            # audio." and kills the whole player loop.
            state.play_next_event.set()

        await self.refresh_status_message(ctx.guild.id, force_repost=True)

        if len(added_tracks) == 1:
            track = added_tracks[0]
            if state.voice_client.is_playing() or state.voice_client.is_paused():
                msg = f"➕ Added to queue: **{track.title}** ({track.duration_str()})"
            else:
                msg = f"🎶 Loading: **{track.title}** ({track.duration_str()})"
        else:
            msg = f"➕ Added **{len(added_tracks)}** {multi_label} to the queue."
            if skipped:
                msg += f" Skipped {skipped} that {skip_reason}."
            if truncated and cap:
                msg += f" Only queued the first {cap} tracks."

        if extra_note:
            msg += f"\n{extra_note}"
        await ctx.reply(msg)

    def format_duration(self, seconds: float | None) -> str:
        if seconds is None or seconds <= 0:
            return "0:00"
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def build_status_embed(self, state: GuildMusicState) -> discord.Embed:
        if not state.current:
            return discord.Embed(title="🎵 Queue", description="No song playing right now.", color=0x000000)

        total = float(state.current.duration or 0)
        elapsed = state.get_elapsed_seconds()
        remaining = max(0.0, total - elapsed) if total else 0.0
        status = "⏸️ Paused" if state.voice_client and state.voice_client.is_paused() else "▶️ Playing"

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{state.current.title}**\nRequested by {state.current.requester.mention}",
            color=0x000000,
        )

        if total > 0:
            progress = min(1.0, max(0.0, elapsed / total))
            bar_length = 18
            filled = int(progress * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            embed.add_field(
                name=f"{status} · {self.format_duration(elapsed)} elapsed",
                value=f"{bar}\nTime left: {self.format_duration(remaining)}",
                inline=False,
            )
        else:
            embed.add_field(name=status, value="Live / duration unavailable", inline=False)

        if state.queue:
            next_items = list(state.queue)[:3]
            next_text = ", ".join(track.title for track in next_items)
            embed.set_footer(text=f"Up next: {next_text}")

        loop_note = None
        if state.loop_current:
            loop_note = "🔂 Looping this track"
        elif state.loop_queue:
            loop_note = "🔁 Looping the queue"
        if loop_note:
            existing_footer = embed.footer.text if embed.footer else None
            embed.set_footer(text=f"{existing_footer} · {loop_note}" if existing_footer else loop_note)

        if state.queue:
            queue_lines = [f"{i + 1}. {track.title} ({track.duration_str()})" for i, track in enumerate(list(state.queue)[:5])]
            embed.add_field(name="Queue", value="\n".join(queue_lines), inline=False)

        return embed

    async def refresh_status_message(self, guild_id: int, *, force_repost: bool = False):
        state = self.get_state(guild_id)
        async with state.status_lock:
            if not state.current:
                if state.status_message:
                    try:
                        await state.status_message.delete()
                    except discord.HTTPException:
                        pass
                    state.status_message = None
                return

            if state.text_channel is None:
                return

            embed = self.build_status_embed(state)
            view = NowPlayingView(self, guild_id)

            if state.status_message and not force_repost:
                try:
                    await state.status_message.edit(embed=embed, view=view)
                    return
                except discord.NotFound:
                    state.status_message = None

            if state.status_message and force_repost:
                try:
                    await state.status_message.delete()
                except discord.HTTPException:
                    pass
                state.status_message = None

            try:
                state.status_message = await state.text_channel.send(embed=embed, view=view)
            except discord.HTTPException:
                pass

    async def refresh_status_for_guild(self, guild_id: int):
        await self.refresh_status_message(guild_id)

    async def skip_track(self, guild_id: int):
        state = self.get_state(guild_id)
        if not state.voice_client or not (state.voice_client.is_playing() or state.voice_client.is_paused()):
            return
        state.loop_current = False
        state.voice_client.stop()
        await self.refresh_status_for_guild(guild_id)

    async def toggle_pause(self, guild_id: int):
        state = self.get_state(guild_id)
        if not state.voice_client:
            return

        if state.voice_client.is_playing():
            state.elapsed_before_pause = state.get_elapsed_seconds()
            state.voice_client.pause()
            state.started_at = None
        elif state.voice_client.is_paused():
            state.started_at = time.monotonic()
            state.voice_client.resume()

        await self.refresh_status_for_guild(guild_id)

    async def toggle_loop(self, guild_id: int) -> bool:
        """Toggles single-track loop. Turns off queue loop if it was on -
        the two modes are mutually exclusive. Returns the new state."""
        state = self.get_state(guild_id)
        state.loop_current = not state.loop_current
        if state.loop_current:
            state.loop_queue = False
        await self.refresh_status_for_guild(guild_id)
        return state.loop_current

    async def toggle_queue_loop(self, guild_id: int) -> bool:
        """Toggles whole-queue loop. Turns off single-track loop if it
        was on. Returns the new state."""
        state = self.get_state(guild_id)
        state.loop_queue = not state.loop_queue
        if state.loop_queue:
            state.loop_current = False
        await self.refresh_status_for_guild(guild_id)
        return state.loop_queue

    async def stop_music(self, guild_id: int):
        state = self.get_state(guild_id)
        state.queue.clear()
        state.loop_current = False
        state.current = None
        state.started_at = None
        state.elapsed_before_pause = 0.0
        state.cancel_status_refresh_loop()
        if state.player_task:
            state.player_task.cancel()
            state.player_task = None
        if state.voice_client and state.voice_client.is_connected():
            await state.voice_client.disconnect()
        if state.status_message:
            try:
                await state.status_message.delete()
            except discord.HTTPException:
                pass
            state.status_message = None

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Plays a song by name or URL, queues it if something's already
        playing, or - given a YouTube or Spotify playlist/album URL -
        queues every track in it."""
        state = await self.ensure_voice(ctx)
        if not state:
            return

        MAX_PLAYLIST_TRACKS = 100

        spotify_match = SPOTIFY_URL_RE.search(query)
        if spotify_match:
            kind, spotify_id = spotify_match.groups()

            # Track/album lookups go through the official Web API and need
            # your app credentials. Playlists don't - they're handled by
            # spotify_scraper below, which needs no credentials at all.
            if kind != "playlist" and not self.spotify:
                await ctx.reply(
                    "Spotify machi configuri f had bot daba bach ndir tracks/albums - "
                    "khass SPOTIFY_CLIENT_ID w SPOTIFY_CLIENT_SECRET (mn "
                    "https://developer.spotify.com/dashboard). Playlists khedamin bla hadchi."
                )
                return

            truncated = False
            async with ctx.typing():
                try:
                    if kind == "track":
                        info = await self.spotify.get_track(spotify_id)
                        spotify_tracks = [info] if info else []
                    elif kind == "album":
                        spotify_tracks = await self.spotify.get_album_tracks(spotify_id)
                        truncated = len(spotify_tracks) > MAX_PLAYLIST_TRACKS
                        spotify_tracks = spotify_tracks[:MAX_PLAYLIST_TRACKS]
                    else:
                        # Spotify's Feb 2026 API changes only return a
                        # playlist's contents to its owner/a collaborator -
                        # Client Credentials auth can never be either, so
                        # this reads the public playlist page instead.
                        # (Episodes and local files are filtered out by
                        # the library itself, before we ever see them.)
                        playlist = await self.spotify_scraper.get_playlist(
                            spotify_id, max_tracks=MAX_PLAYLIST_TRACKS
                        )
                        spotify_tracks = [
                            {
                                "title": pt.track.name,
                                "artist": ", ".join(a.name for a in pt.track.artists),
                                "duration_ms": pt.track.duration_ms,
                            }
                            for pt in playlist.tracks
                        ]
                        truncated = (playlist.total_tracks or 0) > len(spotify_tracks)
                except NotFoundError:
                    await ctx.reply("Ma lqitch had l'playlist f Spotify - tup, khawya, wla private bezzaf.")
                    return
                except SpotifyScraperError as e:
                    await ctx.reply(f"Ma9dertch njib had l'playlist mn Spotify: `{_clean_ytdl_message(e)}`")
                    return
                except Exception as e:
                    await ctx.reply(f"Ma9dertch njib info mn Spotify: `{_clean_ytdl_message(e)}`")
                    return

                if not spotify_tracks:
                    await ctx.reply("Had l'link f Spotify khawi (walo n9dr nzid) wla ghalat.")
                    return

                # No YouTube-matching here anymore: each track becomes a
                # lightweight placeholder (title/duration already known
                # from Spotify) and gets matched to a YouTube stream lazily
                # in the player loop, right before its own turn to play.
                # Previously this awaited every track's match (throttled
                # 4-at-a-time) before queueing ANY of them - for a big
                # playlist that meant a long wait before track #1 even
                # started, which is the bug this fixes.
                added_tracks = [
                    Track.from_spotify(t["title"], t["artist"], t.get("duration_ms"), ctx.author)
                    for t in spotify_tracks
                ]

            await self._queue_and_announce(
                ctx,
                state,
                added_tracks,
                truncated=truncated,
                cap=MAX_PLAYLIST_TRACKS,
                multi_label="tracks from Spotify",
                skip_reason="couldn't be matched on YouTube",
            )
            return

        async with ctx.typing():
            # Peek at just the FIRST entry instead of listing the whole
            # thing up front. For a plain video/search term this already
            # returns full info (yt-dlp only flattens nested playlist
            # entries). For a playlist link this is a much cheaper request
            # than listing all N videos, and is the fix for the multi-
            # second delay before track #1 could start on a big playlist.
            try:
                head_data, head_logger = await self._extract_ytdl(query, playlist_items="1")
            except Exception as e:
                await ctx.reply(f"Ma9dertch nlqa had l'video: `{_clean_ytdl_message(e)}`")
                return

            if head_data is None:
                await ctx.reply(f"Ma9dertch nlqa had l'video: `{head_logger.last_error or 'No results found.'}`")
                return

            if "entries" in head_data:
                head_entries = [e for e in head_data["entries"] if e]
                if not head_entries:
                    await ctx.reply("Ma lqitch walo.")
                    return
                first_entry = head_entries[0]
                is_playlist_link = _looks_like_playlist_query(query)
            else:
                first_entry = head_data
                is_playlist_link = False

            first_track = Track.from_entry(first_entry, ctx.author)
            extra_note = None

            if is_playlist_link:
                # Let the player loop lazily resolve track #1 itself (same
                # as every other playlist entry) instead of blocking here -
                # and fetch tracks 2..N in the background so they show up
                # in the queue shortly after, without holding up playback.
                self.bot.loop.create_task(self._fill_playlist_remainder(ctx, query, MAX_PLAYLIST_TRACKS))
                extra_note = "📃 Loading the rest of the playlist in the background..."
            else:
                # Plain single video or a search term: resolve it right
                # away so the "Loading: X (3:45)" confirmation shows
                # accurate info immediately, same as before this fix.
                if not first_track.url:
                    await self._resolve_track(first_track)

            added_tracks = [first_track]

        await self._queue_and_announce(
            ctx,
            state,
            added_tracks,
            cap=MAX_PLAYLIST_TRACKS,
            multi_label="tracks",
            skip_reason="couldn't be loaded (private/age-restricted/removed)",
            extra_note=extra_note,
        )

    @commands.command(name="skip", aliases=["next", "sk"], hidden=True)
    async def skip(self, ctx: commands.Context):
        await self.skip_track(ctx.guild.id)
        await ctx.reply("⏭️ Skipped.")

    @commands.command(name="pause", hidden=True)
    async def pause(self, ctx: commands.Context):
        await self.toggle_pause(ctx.guild.id)
        await ctx.reply("⏸️ Toggled pause.")

    @commands.command(name="resume", hidden=True)
    async def resume(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_paused():
            state.started_at = time.monotonic()
            state.voice_client.resume()
            await self.refresh_status_for_guild(ctx.guild.id)
            await ctx.reply("▶️ Resumed.")
        else:
            await ctx.reply("Machi paused daba.")

    @commands.command(name="stop", hidden=True)
    async def stop(self, ctx: commands.Context):
        await self.stop_music(ctx.guild.id)
        await ctx.reply("⏹️ Stopped and left the channel.")

    @commands.command(name="queue", aliases=["q"], hidden=True)
    async def queue_(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.current and not state.queue:
            await ctx.reply("Queue khawya.")
            return

        lines = []
        if state.current:
            lines.append(f"**Now playing:** {state.current.title} ({state.current.duration_str()})")
        if state.queue:
            lines.append("")
            lines.append("**Up next:**")
            for i, t in enumerate(list(state.queue)[:10], start=1):
                lines.append(f"{i}. {t.title} ({t.duration_str()}) — added by {t.requester.display_name}")
            if len(state.queue) > 10:
                lines.append(f"...and {len(state.queue) - 10} more")

        embed = discord.Embed(description="\n".join(lines), color=0x000000, title="🎵 Queue")
        await ctx.reply(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"], hidden=True)
    async def nowplaying(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.current:
            await ctx.reply("Walo li kaytzad daba.")
            return

        # From now on, keep updating/posting the status message in the
        # channel /np was called from.
        state.text_channel = ctx.channel
        # force_repost=True deletes whatever status message currently
        # exists (in any channel) before posting the new one, under the
        # status_lock, so there's never more than one instance live.
        await self.refresh_status_message(ctx.guild.id, force_repost=True)

    @commands.command(name="volume", aliases=["vol"], hidden=True)
    async def volume(self, ctx: commands.Context, percent: int):
        state = self.get_state(ctx.guild.id)
        percent = max(0, min(percent, 150))
        state.volume = percent / 100
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        await ctx.reply(f"🔊 Volume set to {percent}%.")

    @commands.command(name="loop", hidden=True)
    async def loop(self, ctx: commands.Context):
        enabled = await self.toggle_loop(ctx.guild.id)
        await ctx.reply(f"🔂 Track loop {'enabled' if enabled else 'disabled'}.")

    @commands.command(name="queueloop", aliases=["qloop", "loopqueue"], hidden=True)
    async def queueloop(self, ctx: commands.Context):
        enabled = await self.toggle_queue_loop(ctx.guild.id)
        await ctx.reply(f"🔁 Queue loop {'enabled' if enabled else 'disabled'}.")

    @commands.command(name="join", hidden=True)
    async def join(self, ctx: commands.Context):
        state = await self.ensure_voice(ctx)
        if state:
            await ctx.reply(f"Dkhalt l {ctx.author.voice.channel.mention}.")

    @commands.command(name="leave", aliases=["leavevc", "stopmusic"], hidden=True)
    async def leave(self, ctx: commands.Context):
        await self.stop_music(ctx.guild.id)
        await ctx.reply("⏹️ Stopped and left the channel.")


async def setup(bot):
    await bot.add_cog(Music(bot))