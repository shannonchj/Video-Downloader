from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest
from check_forbidden import FORBIDDEN_YTDLP_KEYS
from yt_dlp.utils import DownloadError, ExtractorError

from mediabot.config import Settings
from mediabot.downloader.runner import DownloadFailed, run

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VID = "dQw4w9WgXcQ"


class FakeYdl:
    def __init__(
        self,
        opts: dict[str, Any],
        info: dict[str, Any],
        *,
        content: bytes = b"data",
        filepath: Callable[[Path], Path] | None = None,
        error: Exception | None = None,
        progress: list[dict[str, Any]] | None = None,
    ) -> None:
        self.opts = opts
        self.info = info
        self.content = content
        self.filepath = filepath
        self.error = error
        self.progress = progress or []

    def __enter__(self) -> FakeYdl:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        assert url == URL
        assert download is True
        if self.error is not None:
            raise self.error
        info = dict(self.info)
        match_filter = self.opts["match_filter"]
        if match_filter(info, incomplete={"url", "filesize"}) is not None:
            return info
        if match_filter(info, incomplete=False) is not None:
            return info
        for d in self.progress:
            for hook in self.opts["progress_hooks"]:
                hook(d)
        home = Path(self.opts["paths"]["home"])
        out = self.filepath(home) if self.filepath else home / f"{info['id']}.{info['ext']}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(self.content)
        info["requested_downloads"] = [{"filepath": str(out)}]
        return info


def make_settings(tmp_path: Path, **overrides: int) -> Settings:
    return Settings(_env_file=None, vault_dir=tmp_path, **overrides)


def info(**fields: Any) -> dict[str, Any]:
    return {"id": VID, "ext": "mp4", "title": "A title", "duration": 60, **fields}


def factory(
    captured: list[FakeYdl], video: dict[str, Any], **kwargs: Any
) -> Callable[[dict[str, Any]], FakeYdl]:
    def make(opts: dict[str, Any]) -> FakeYdl:
        ydl = FakeYdl(opts, video, **kwargs)
        captured.append(ydl)
        return ydl

    return make


def test_successful_download(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    result = run(URL, "video_mp4", settings=settings, ydl_factory=factory([], info()))
    assert result.video_id == VID
    assert result.title == "A title"
    assert result.path == (settings.download_dir / f"{VID}.mp4").resolve()
    assert result.size_bytes == 4
    assert settings.work_dir.is_dir()


def test_opts_merge_base_and_preset(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    captured: list[FakeYdl] = []
    run(URL, "audio_m4a", settings=settings, ydl_factory=factory(captured, info(ext="m4a")))
    opts = captured[0].opts
    assert opts["outtmpl"] == {"default": "%(id)s.%(ext)s"}
    assert opts["paths"] == {"home": str(settings.download_dir), "temp": str(settings.work_dir)}
    assert opts["noplaylist"] is True
    assert opts["max_filesize"] == settings.max_filesize_bytes
    assert opts["format"] == "ba[ext=m4a]/ba"
    assert opts["postprocessors"] == [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
    assert Path(opts["js_runtimes"]["deno"]["path"]).is_file()
    assert "remote_components" not in opts
    assert not set(opts) & FORBIDDEN_YTDLP_KEYS


def test_unknown_preset_is_rejected_before_download(tmp_path: Path) -> None:
    captured: list[FakeYdl] = []
    with pytest.raises(Exception, match="unknown_preset"):
        run(URL, "nope", settings=make_settings(tmp_path), ydl_factory=factory(captured, info()))
    assert captured == []


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"is_live": True}, "live_not_supported"),
        ({"was_live": True}, "live_not_supported"),
        ({"duration": 61}, "too_long"),
        ({"filesize": 101}, "file_too_large"),
        ({"filesize_approx": 101.5}, "file_too_large"),
        (
            {"requested_formats": [{"filesize": 60}, {"filesize_approx": 41}]},
            "file_too_large",
        ),
    ],
)
def test_rejected_by_filter(tmp_path: Path, fields: dict[str, Any], code: str) -> None:
    settings = make_settings(tmp_path, max_duration_seconds=60, max_filesize_bytes=100)
    with pytest.raises(DownloadFailed) as exc_info:
        run(URL, "video_mp4", settings=settings, ydl_factory=factory([], info(**fields)))
    assert exc_info.value.code == code
    assert list(settings.download_dir.iterdir()) == []


def test_filesize_precheck_skipped_when_unknown(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, max_filesize_bytes=100)
    video = info(requested_formats=[{"filesize": 60}, {}])
    result = run(URL, "video_mp4", settings=settings, ydl_factory=factory([], video))
    assert result.size_bytes == 4


def test_actual_file_over_limit_is_deleted(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, max_filesize_bytes=3)
    with pytest.raises(DownloadFailed) as exc_info:
        run(URL, "video_mp4", settings=settings, ydl_factory=factory([], info(), content=b"1234"))
    assert exc_info.value.code == "file_too_large"
    assert list(settings.download_dir.iterdir()) == []


def _raise_wrapped(cause: Exception) -> DownloadError:
    try:
        raise cause
    except Exception:
        return DownloadError(str(cause), sys.exc_info())


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (_raise_wrapped(ExtractorError("Video unavailable", expected=True)), "unavailable"),
        (_raise_wrapped(ExtractorError("bug", expected=False)), "download_error"),
        (_raise_wrapped(OSError("network")), "download_error"),
        (DownloadError("no exc info"), "download_error"),
    ],
)
def test_download_errors_are_classified(tmp_path: Path, error: Exception, code: str) -> None:
    with pytest.raises(DownloadFailed) as exc_info:
        run(
            URL,
            "video_mp4",
            settings=make_settings(tmp_path),
            ydl_factory=factory([], info(), error=error),
        )
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    "filepath",
    [
        lambda home: home.parent / "outside" / f"{VID}.mp4",
        lambda home: home / "Some Title.mp4",
        lambda home: home / "sub" / ".." / ".." / f"{VID}.mp4",
    ],
)
def test_unexpected_output_path_fails(tmp_path: Path, filepath: Callable[[Path], Path]) -> None:
    with pytest.raises(DownloadFailed) as exc_info:
        run(
            URL,
            "video_mp4",
            settings=make_settings(tmp_path),
            ydl_factory=factory([], info(), filepath=filepath),
        )
    assert exc_info.value.code == "output_missing"


def test_missing_requested_downloads_fails(tmp_path: Path) -> None:
    class NoOutput(FakeYdl):
        def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
            return dict(self.info)

    with pytest.raises(DownloadFailed) as exc_info:
        run(
            URL,
            "video_mp4",
            settings=make_settings(tmp_path),
            ydl_factory=lambda opts: NoOutput(opts, info()),
        )
    assert exc_info.value.code == "output_missing"


def test_progress_callback_receives_percentages(tmp_path: Path) -> None:
    seen: list[float] = []
    progress = [
        {"status": "downloading", "downloaded_bytes": 25, "total_bytes": 100},
        {"status": "downloading", "downloaded_bytes": 50, "total_bytes_estimate": 200},
        {"status": "downloading", "downloaded_bytes": 10},
        {"status": "downloading", "downloaded_bytes": 300, "total_bytes": 200},
        {"status": "finished", "downloaded_bytes": 100, "total_bytes": 100},
    ]
    run(
        URL,
        "video_mp4",
        settings=make_settings(tmp_path),
        progress_cb=seen.append,
        ydl_factory=factory([], info(), progress=progress),
    )
    assert seen == [25.0, 25.0, 100.0]
