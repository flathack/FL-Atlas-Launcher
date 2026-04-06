from __future__ import annotations

import logging
from pathlib import Path
import re
from urllib.error import URLError
from urllib.request import Request, urlopen


class RemoteLinkService:
    DISCORD_WIKI_URL = "https://github.com/flathack/FLAtlas/wiki/DiscordLink"
    DISCORD_FALLBACK_URL = "https://discord.gg/QaPAUWPb"
    _DISCORD_PATTERN = re.compile(r"https://discord\.gg/[A-Za-z0-9]+")

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.logger = logging.getLogger("fl_atlas.remote_links")

    @property
    def discord_cache_path(self) -> Path:
        return self.cache_dir / "discord-link.txt"

    def discord_invite_url(self) -> str:
        cached_value = self._read_cache()
        remote_value = self._fetch_discord_invite()
        if remote_value:
            self._write_cache(remote_value, previous_value=cached_value)
            return remote_value

        if cached_value:
            self.logger.info("Using cached Discord invite URL")
            return cached_value

        self.logger.warning("Using fallback Discord invite URL")
        return self.DISCORD_FALLBACK_URL

    def _fetch_discord_invite(self) -> str:
        request = Request(
            self.DISCORD_WIKI_URL,
            headers={"User-Agent": "FL-Atlas-Launcher/0.4.0"},
        )
        try:
            with urlopen(request, timeout=5) as response:
                content = response.read().decode("utf-8", errors="replace")
        except (OSError, URLError) as error:
            self.logger.warning("Failed to fetch Discord wiki page: %s", error)
            return ""

        match = self._DISCORD_PATTERN.search(content)
        if not match:
            self.logger.warning("No Discord invite URL found on wiki page")
            return ""
        return match.group(0)

    def _read_cache(self) -> str:
        try:
            value = self.discord_cache_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        if self._DISCORD_PATTERN.fullmatch(value):
            return value
        return ""

    def _write_cache(self, value: str, previous_value: str = "") -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.discord_cache_path.write_text(value, encoding="utf-8")
        except OSError as error:
            self.logger.warning("Failed to write Discord link cache: %s", error)
            return

        if value != previous_value:
            if previous_value:
                self.logger.info("Discord invite URL updated from wiki: %s -> %s", previous_value, value)
            else:
                self.logger.info("Discord invite URL cached from wiki: %s", value)
