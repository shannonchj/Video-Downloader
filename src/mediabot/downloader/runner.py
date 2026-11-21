"""Run a single download through the yt-dlp Python API (docs/PLAN.md §7.5, S4, S8, S12)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, Self

import deno
import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from mediabot.config import Settings
from mediabot.downloader.presets import get_preset
from mediabot.errors import MediabotError

log = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]


class YdlLike(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> object: ...

    def extract_info(self, url: str, download: bool = ...) -> Any: ...


YdlFactory = Callable[[dict[str, object]], YdlLike]


class DownloadFailed(MediabotError):
    pass


@dataclass(frozen=True)
class DownloadResult:
    video_id: str
    title: str | None
    path: Path
    size_bytes: int


class _YdlLogger:
    _log = logging.getLogger("mediabot.downloader.ytdlp")

    def debug(self, msg: str) -> None:
        self._log.debug(msg)

    def info(self, msg: str) -> None:
        self._log.debug(msg)

    def warning(self, msg: str) -> None:
        self._log.warning(msg)

    def error(self, msg: str) -> None:
        self._log.error(msg)


def _base_opts(settings: Settings) -> dict[str, object]:
    return {
        "outtmpl": {"default": "%(id)s.%(ext)s"},
        "paths": {"home": str(settings.download_dir), "temp": str(settings.work_dir)},
        "noplaylist": True,
        "max_filesize": settings.max_filesize_bytes,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 3,
        "sleep_interval_requests": 1,
        "js_runtimes": {"deno": {"path": deno.find_deno_bin()}},
        "logger": _YdlLogger(),
    }


def _estimated_size(info: Mapping[str, Any]) -> int | None:
    formats = info.get("requested_formats") or [info]
    total = 0
    for fmt in formats:
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if not isinstance(size, int | float):
            return None
        total += int(size)
    return total


class _Filter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.rejected: str | None = None

    def __call__(self, info: Mapping[str, Any], *, incomplete: object) -> str | None:
        code = self._check(info, incomplete=bool(incomplete))
        if code is not None and self.rejected is None:
            self.rejected = code
        return code

    def _check(self, info: Mapping[str, Any], *, incomplete: bool) -> str | None:
        if info.get("is_live") or info.get("was_live"):
            return "live_not_supported"
        duration = info.get("duration") or 0
        if duration > self._settings.max_duration_seconds:
            return "too_long"
        if not incomplete:
            size = _estimated_size(info)
            if size is not None and size > self._settings.max_filesize_bytes:
                return "file_too_large"
        return None


def _progress_hook(cb: ProgressCallback) -> Callable[[Mapping[str, Any]], None]:
    def hook(d: Mapping[str, Any]) -> None:
        if d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        done = d.get("downloaded_bytes")
        if not total or done is None:
            return
        cb(min(100.0, 100.0 * done / total))

    return hook


def _classify(err: Exception) -> str:
    exc_info = getattr(err, "exc_info", None)
    cause = exc_info[1] if exc_info else None
    if isinstance(cause, ExtractorError) and cause.expected:
        return "unavailable"
    return "download_error"


def _output_path(info: Mapping[str, Any], download_dir: Path) -> Path:
    downloads = info.get("requested_downloads") or []
    raw = downloads[0].get("filepath") if downloads else None
    if not raw:
        raise DownloadFailed("output_missing", "no filepath reported")
    path = Path(raw).resolve()
    if not path.is_relative_to(download_dir.resolve()):
        raise DownloadFailed("output_missing", "output outside download dir")
    if path.stem != info.get("id") or not path.is_file():
        raise DownloadFailed("output_missing", "unexpected output file")
    return path


def run(
    canonical_url: str,
    preset: str,
    *,
    settings: Settings,
    progress_cb: ProgressCallback | None = None,
    ydl_factory: YdlFactory = yt_dlp.YoutubeDL,
) -> DownloadResult:
    match_filter = _Filter(settings)
    opts: dict[str, object] = {
        **_base_opts(settings),
        **get_preset(preset).build_opts(),
        "match_filter": match_filter,
        "progress_hooks": [_progress_hook(progress_cb)] if progress_cb else [],
    }
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    settings.work_dir.mkdir(parents=True, exist_ok=True)

    try:
        with ydl_factory(opts) as ydl:
            info = ydl.extract_info(canonical_url, download=True)
    except DownloadError as err:
        raise DownloadFailed(_classify(err), str(err)) from None

    if match_filter.rejected is not None:
        raise DownloadFailed(match_filter.rejected)
    if not isinstance(info, Mapping):
        raise DownloadFailed("output_missing", "no info returned")

    path = _output_path(info, settings.download_dir)
    size = path.stat().st_size
    if size > settings.max_filesize_bytes:
        path.unlink()
        raise DownloadFailed("file_too_large")

    title = info.get("title")
    log.info("downloaded %s (%d bytes)", path.name, size)
    return DownloadResult(
        video_id=str(info["id"]),
        title=title if isinstance(title, str) else None,
        path=path,
        size_bytes=size,
    )
