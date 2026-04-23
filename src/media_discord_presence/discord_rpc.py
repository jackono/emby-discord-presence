import json
import time

from pypresence import Presence
from pypresence.payloads import Payload

from .external_links import ExternalLinksResolver
from .models import PlaybackState


class DiscordRPC:
    def __init__(self, discord_config: dict):
        self.discord_config = discord_config
        self.client_id = str(discord_config.get("client_id", ""))
        self.rpc = None
        self.last_payload = None
        self.last_session_id = None
        self.links = ExternalLinksResolver(
            omdb_api_key=str(discord_config.get("omdb_api_key", "")),
            auto_buttons=discord_config.get("auto_buttons", {}),
        )

    def ensure_connected(self):
        if self.rpc is not None:
            return
        if not self.client_id:
            raise RuntimeError("discord.client_id is missing in config.json")
        self.rpc = Presence(self.client_id)
        self.rpc.connect()

    def build_payload(self, playback: PlaybackState) -> dict:
        verb = "Paused" if playback.paused else "Watching"
        device_and_client = _join_unique(playback.device_name, playback.client_name)
        templates = self.discord_config.get("templates", {})

        if playback.media_type == "Episode" and playback.series:
            details = self._render_template(templates.get("episode_details", "{title}"), playback)
            state = self._render_template(
                templates.get("episode_state", "{show} • {se} • {device_client}"),
                playback,
                device_client=device_and_client,
            )
        elif playback.media_type == "Movie":
            details = self._render_template(templates.get("movie_details", "{title}{year_suffix}"), playback)
            state = self._render_template(
                templates.get("movie_state", "{device_client}"),
                playback,
                device_client=device_and_client,
            )
        elif playback.media_type == "Track":
            details = self._render_template(templates.get("track_details", "{title}"), playback)
            state = self._render_template(
                templates.get("track_state", "{artist} • {album} • {device_client}"),
                playback,
                device_client=device_and_client,
            )
        else:
            details = self._render_template(templates.get("default_details", "{title}"), playback)
            state = self._render_template(
                templates.get("default_state", "{device_client}"),
                playback,
                device_client=device_and_client,
            )

        payload = {
            "details": details[:128],
            "state": state[:128],
            "large_text": f"{verb} {playback.client_name}"[:128],
        }

        large_image = playback.artwork_url or self.discord_config.get("large_image")
        small_image = self.discord_config.get("small_image")
        small_text = self.discord_config.get("small_text") or f"{verb} on {device_and_client}"
        if large_image:
            payload["large_image"] = large_image
        if small_image:
            payload["small_image"] = small_image
            payload["small_text"] = small_text[:128]

        if playback.duration_seconds > 0 and playback.position_seconds >= 0 and not playback.paused:
            start_time = int(time.time() - playback.position_seconds)
            payload["start"] = start_time
            payload["end"] = int(start_time + playback.duration_seconds)

        buttons = list(self.discord_config.get("buttons", []))
        self._append_auto_buttons(buttons, playback)
        if buttons:
            payload["buttons"] = buttons[:2]

        return payload

    def update(self, playback: PlaybackState):
        payload = self.build_payload(playback)
        self.ensure_connected()
        if payload == self.last_payload and playback.session_id == self.last_session_id:
            return
        self.rpc.update(payload_override=self._build_activity_payload(payload, playback))
        self.last_payload = payload
        self.last_session_id = playback.session_id
        print(f"Updated presence: {json.dumps(payload, ensure_ascii=False)}", flush=True)

    def clear(self):
        if self.rpc is None:
            return
        try:
            self.rpc.clear()
        except Exception:
            pass
        self.last_payload = None
        self.last_session_id = None

    def reset(self):
        try:
            if self.rpc is not None:
                self.rpc.close()
        except Exception:
            pass
        self.rpc = None

    def _append_auto_buttons(self, buttons: list[dict], playback: PlaybackState):
        if len(buttons) >= 2:
            return

        lookup_title = playback.series if playback.media_type == "Episode" and playback.series else playback.title
        if not playback.imdb_url:
            playback.imdb_url = self.links.resolve_imdb_url(lookup_title, playback.year, playback.media_type == "Movie")
        if not playback.mal_url:
            playback.mal_url = self.links.resolve_mal_url(lookup_title)

        candidates = [
            ("IMDb", playback.imdb_url),
            ("MyAnimeList", playback.mal_url),
        ]
        seen_urls = {str(button.get("url", "")).strip() for button in buttons}
        for label, url in candidates:
            if len(buttons) >= 2:
                break
            if not url or url in seen_urls:
                continue
            buttons.append({"label": label, "url": url})
            seen_urls.add(url)

    def _render_template(self, template: str, playback: PlaybackState, **extras) -> str:
        values = _TemplateValues(
            title=playback.title or "",
            show=playback.series or "",
            season=_stringify(playback.season),
            episode=_stringify(playback.episode),
            se=_episode_code(playback),
            year=_stringify(playback.year),
            year_suffix=f" ({playback.year})" if playback.year else "",
            genres=", ".join(playback.genres),
            artist=playback.artist or "",
            album=playback.album or "",
            device=playback.device_name or "",
            client=playback.client_name or "",
            paused="true" if playback.paused else "false",
            **extras,
        )
        return _collapse_separators(template.format_map(values))

    def _build_activity_payload(self, payload: dict, playback: PlaybackState) -> dict:
        rpc_payload = Payload.set_activity(
            state=payload.get("state"),
            details=payload.get("details"),
            start=payload.get("start"),
            end=payload.get("end"),
            large_image=payload.get("large_image"),
            large_text=payload.get("large_text"),
            small_image=payload.get("small_image"),
            small_text=payload.get("small_text"),
            buttons=payload.get("buttons"),
            instance=True,
        ).data
        activity = rpc_payload.get("args", {}).get("activity", {})
        activity["type"] = _activity_type(playback)
        activity["status_display_type"] = _status_display_type(self.discord_config, playback)
        return rpc_payload


def _join_unique(*parts: str) -> str:
    result = []
    seen = set()
    for part in parts:
        value = (part or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return " • ".join(result)


class _TemplateValues(dict):
    def __missing__(self, key):
        return ""


def _episode_code(playback: PlaybackState) -> str:
    if playback.season is None or playback.episode is None:
        return ""
    return f"S{int(playback.season):02d}E{int(playback.episode):02d}"


def _stringify(value) -> str:
    return "" if value is None else str(value)


def _collapse_separators(value: str) -> str:
    parts = [part.strip() for part in value.split("•")]
    filtered = [part for part in parts if part]
    return " • ".join(filtered).strip(" -|")


def _activity_type(playback: PlaybackState) -> int:
    if playback.media_type == "Track":
        return 2
    return 3


def _status_display_type(discord_config: dict, playback: PlaybackState) -> int:
    configured = str(discord_config.get("status_display", "auto")).strip().lower()
    if configured == "name":
        return 0
    if configured == "state":
        return 1
    if configured == "details":
        return 2

    if playback.media_type == "Episode":
        return 1
    return 2
