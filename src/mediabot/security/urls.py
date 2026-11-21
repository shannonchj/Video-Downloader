"""URL validation and canonicalisation (docs/PLAN.md §7.3, S5)."""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from urllib.parse import parse_qs, urlsplit

from mediabot.errors import MediabotError

ALLOWED_HOSTS = frozenset({"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"})
MAX_URL_LEN = 300
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class InvalidURL(MediabotError):
    pass


def _has_bad_chars(raw: str) -> bool:
    return any(ch.isspace() or unicodedata.category(ch).startswith("C") for ch in raw)


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def validate_url(raw: str) -> str:
    """Return https://www.youtube.com/watch?v=<id>, or raise InvalidURL."""
    if len(raw) > MAX_URL_LEN:
        raise InvalidURL("url_too_long")
    if _has_bad_chars(raw):
        raise InvalidURL("bad_chars")
    u = urlsplit(raw)
    if u.scheme != "https" or u.username is not None or u.password is not None:
        raise InvalidURL("scheme_or_auth")
    try:
        port = u.port
    except ValueError:
        raise InvalidURL("bad_port") from None
    if port is not None:
        raise InvalidURL("bad_port")
    host = (u.hostname or "").lower()
    if _is_ip(host):
        raise InvalidURL("ip_host")
    if host not in ALLOWED_HOSTS:
        raise InvalidURL("host_not_allowed")

    if host == "youtu.be":
        vid = u.path.lstrip("/").split("/")[0]
    elif u.path.startswith("/shorts/"):
        parts = u.path.split("/")
        vid = parts[2] if len(parts) > 2 else ""
    else:
        vid = parse_qs(u.query).get("v", [""])[0]
    if not VIDEO_ID_RE.match(vid):
        raise InvalidURL("bad_video_id")
    return f"https://www.youtube.com/watch?v={vid}"
