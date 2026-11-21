from pathlib import Path
from typing import Any

import pytest

from mediabot.config import Settings
from mediabot.downloader import __main__ as cli
from mediabot.downloader.runner import DownloadFailed, DownloadResult

URL = "https://youtu.be/dQw4w9WgXcQ"


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    settings = Settings(_env_file=None, vault_dir=tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    def fake_run(url: str, preset: str, **kwargs: Any) -> DownloadResult:
        seen.append((url, preset))
        if preset == "audio_m4a":
            raise DownloadFailed("too_long")
        return DownloadResult("dQw4w9WgXcQ", None, tmp_path / "dQw4w9WgXcQ.mp4", 4)

    monkeypatch.setattr(cli, "run", fake_run)
    return seen


def test_success_passes_canonical_url(calls: list[tuple[str, str]]) -> None:
    assert cli.main([URL, "video_mp4"]) == 0
    assert calls == [("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video_mp4")]


def test_download_failure_exits_1(
    calls: list[tuple[str, str]], caplog: pytest.LogCaptureFixture
) -> None:
    assert cli.main([URL, "audio_m4a"]) == 1
    assert "too_long" in caplog.text


def test_invalid_url_exits_2_without_download(calls: list[tuple[str, str]]) -> None:
    assert cli.main(["https://evil.com/?v=dQw4w9WgXcQ", "video_mp4"]) == 2
    assert calls == []


def test_unknown_preset_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, vault_dir=tmp_path))
    assert cli.main([URL, "video_with_subs"]) == 2


def test_missing_arguments_exit_2() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main([URL])
    assert exc_info.value.code == 2
