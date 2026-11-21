import os
from pathlib import Path

import pytest

from mediabot.config import Settings
from mediabot.downloader.runner import DownloadFailed, run
from mediabot.security.urls import validate_url

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("MEDIABOT_IT_URL"),
        reason="set MEDIABOT_IT_URL to a short Creative Commons video",
    ),
]


@pytest.fixture
def url() -> str:
    return validate_url(os.environ["MEDIABOT_IT_URL"])


@pytest.mark.parametrize(("preset", "ext"), [("video_mp4", ".mp4"), ("audio_m4a", ".m4a")])
def test_download_preset(tmp_path: Path, url: str, preset: str, ext: str) -> None:
    settings = Settings(_env_file=None, vault_dir=tmp_path)
    seen: list[float] = []
    result = run(url, preset, settings=settings, progress_cb=seen.append)
    assert result.path.suffix == ext
    assert result.path.name == f"{result.video_id}{ext}"
    assert result.path.parent == settings.download_dir.resolve()
    assert result.size_bytes == result.path.stat().st_size > 0
    assert [p.name for p in settings.download_dir.iterdir()] == [result.path.name]
    assert seen


def test_too_long(tmp_path: Path, url: str) -> None:
    settings = Settings(_env_file=None, vault_dir=tmp_path, max_duration_seconds=1)
    with pytest.raises(DownloadFailed) as exc_info:
        run(url, "video_mp4", settings=settings)
    assert exc_info.value.code == "too_long"
    assert list(settings.download_dir.iterdir()) == []
